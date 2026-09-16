"""Provider selection at the model seam.

Why this module exists
----------------------
Until 2026-09-15 the Python CLI was built on exactly one provider: an Anthropic
API key, or a Claude Code OAuth login harvested from ``~/.claude/.credentials.json``
with claude-cli user-agent and beta headers impersonating the CLI. Every one of
those facts was a module constant in engine.py, and ``agent()`` assembled the
transport itself. Adding GLM 5.3 (Z.ai, Anthropic-compatible endpoint, plain API
key) meant either duplicating that head per provider or giving the facts one home.

The interface is three entry points and deliberately FACTS ONLY::

    select()      -> Spec       which provider, resolved from env (no credential IO)
    transport()   -> Transport  Spec + resolved credential + assembled headers
    describe()    -> str        one line for --selftest and preflight

Everything that is POLICY rather than fact - retries, the corrective re-ask,
``<UNKNOWN>`` sentinel recovery, max_tokens growth, the 429 backoff curve - stays
in ``engine.agent()``. ADR-0001 built that seam for malformed responses; this
module narrows the same seam to provider transport. A third provider that speaks
the Anthropic Messages wire is a row in contract/providers.json and nothing else;
a provider on a different wire needs a real adapter and its own ADR, and none is
pretended to exist here.

Selection rules (in order, and the order is the interface):
  1. ``DR_PROVIDER`` set  -> must name a provider in the contract, or AuthError
     listing the valid names. Explicit beats inference.
  2. Otherwise INFER from disjoint key environments: exactly one provider has a
     key set -> that provider. Both set -> a LOUD refusal naming both variables,
     because guessing between two live credentials bills the wrong account.
  3. Neither set -> the contract default ("claude"), whose credential() still
     falls back to the Claude Code OAuth login file - the path this tool was
     born on, unchanged.

Invariants: with DR_PROVIDER unset and no GLM key set, every byte of the Claude
path is unchanged - same URL, same headers per scheme, same system prefix, same
default model, same AuthError wording - because the prompts were calibrated
against that configuration and an unused option must not perturb it. Every
AuthError names the SELECTED provider's key environment; preflight and selftest
quote these messages verbatim, so a GLM run must never be told to set
ANTHROPIC_API_KEY.
"""
import json
import os
import shutil
import subprocess
import threading
import time

__all__ = ["AuthError", "select", "spec", "transport", "describe", "reset", "names"]

# Same loading convention as contract/depths.json and contract/hypothesis-words.json:
# the contract is the one place the facts live, and an env override exists so tests
# (and only tests) can point at a mutated copy - the pattern DR_CONFORMANCE_FILE set
# for conformance and DR_HYP_WORDS_FILE for the matcher wordlists.
_PROVIDERS_FILE = os.environ.get(
    "DR_PROVIDERS_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "..", "contract", "providers.json"))
with open(os.path.normpath(_PROVIDERS_FILE), encoding="utf-8") as _pf:
    _CONTRACT = json.load(_pf)


class AuthError(RuntimeError):
    """The selected provider's credential is missing, expired or rejected.

    Lives here (not engine) because credential knowledge lives here; engine
    re-exports it so ``pmap``'s never-swallow catch and the tests keep the
    ``engine.AuthError`` name they were written against.
    """


def names():
    """The contract's provider names, in file order - for error text and --provider."""
    return list(_CONTRACT["providers"])


def spec(name):
    p = _CONTRACT["providers"][name]
    s = {
        "name": name,
        "label": p["label"],
        "url": (os.environ.get(p["baseUrlEnv"], "").rstrip("/")
                if p.get("baseUrlEnv") and os.environ.get(p["baseUrlEnv"])
                else p["baseUrl"].rstrip("/")) + "/v1/messages",
        "key_env": p["keyEnvs"][0],
        "key_envs": list(p["keyEnvs"]),
        "key_help": p.get("keyHelp", ""),
        "default_model": p["defaultModel"],
        "base_url_env": p.get("baseUrlEnv", ""),
        "system_prefix": p["systemPrefix"],
        "static_headers": dict(p.get("staticHeaders") or {}),
        "oauth": p.get("oauth"),
        "harness": p.get("harness"),
        # Filled in by _mark_endpoint_owner below when the effective base URL belongs
        # to a DIFFERENT contract provider than the one the credential selected.
        "endpoint_owner": None,
    }
    return _mark_endpoint_owner(s, p)


def harness_command(spec):
    """The full argv prefix that spawns this provider's harness, or None.

    Session-first (ADR-0005): the owner's deployments hold no API keys - model calls
    are powered by a harness CLI's own login (claude -p, hermes -p glm -z). If that
    CLI resolves on this machine, IT is the intended power source and the HTTP path
    is the fallback. Resolution order: the contract's command on PATH; the provider's
    fallbackCommandEnv carrying a full command string (for harnesses that live inside
    a container, e.g. 'docker exec <c> /opt/hermes/.venv/bin/hermes'); else None and
    the seam falls back to key-env/OAuth HTTP. DR_TRANSPORT=http forces HTTP even
    when a harness exists, because a user who holds BOTH may prefer one socket to
    150 spawns.
    """
    if os.environ.get("DR_TRANSPORT", "").strip().lower() == "http":
        return None
    h = spec.get("harness") or {}
    cmd = h.get("command")
    if not cmd:
        return None
    if shutil.which(cmd):
        return [cmd] + list(h.get("args") or [])
    env_cmd = os.environ.get(h.get("fallbackCommandEnv") or "", "").strip()
    if env_cmd:
        head = env_cmd.split()[0]
        if shutil.which(head) or os.path.exists(head):
            return env_cmd.split() + list(h.get("args") or [])
    return None


def run_harness(argv, prompt, timeout=300):
    """One model call through the harness CLI. Returns stdout, or raises.

    The spawn is MECHANISM and lives at the seam; POLICY (retries, the corrective
    re-ask, sentinel recovery, shape()) stays in engine.agent() exactly as it does on
    the HTTP path - ADR-0001 applies to both transports equally. Non-zero exit and
    timeouts raise RuntimeError so agent()'s retry loop can treat them like any other
    failed attempt.
    """
    # A prompt of many kilobyts on the argv would blow ARG_MAX on some harnesses;
    # claude -p and hermes -z both accept it positionally and handle long strings,
    # but be defensive the cheap way.
    proc = subprocess.run(argv + [prompt], capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0 or not (proc.stdout or "").strip():
        raise RuntimeError("harness %r exited %d: %s"
                           % (argv[0], proc.returncode, (proc.stderr or "")[:200]))
    return proc.stdout


def _mark_endpoint_owner(s, p):
    """If the effective base URL belongs to another CONTRACT provider, say so.

    Audited 2026-09-15 on the Telegram deployment: gateways commonly map a Z.ai plan
    key into ANTHROPIC_API_KEY + ANTHROPIC_BASE_URL for subprocesses (the "env shim").
    The engine then resolved to provider=claude, described itself as "Anthropic
    (api-key)" while POSTing to api.z.ai, and defaulted the model to claude-sonnet-5 -
    a name Z.ai happens to tolerate, which is luck, not a configuration. When the
    override host matches a provider named in THIS contract, adopt that provider's
    default model and label the endpoint honestly. An arbitrary relay host matches
    nothing in the contract and leaves everything untouched - a generic proxy is not
    evidence of anyone's semantics.
    """
    host = s["url"].split("/v1/messages")[0]
    for other, op in _CONTRACT["providers"].items():
        if other == s["name"]:
            continue
        base = (os.environ.get(op["baseUrlEnv"], "").rstrip("/")
                if op.get("baseUrlEnv") and os.environ.get(op["baseUrlEnv"])
                else op["baseUrl"].rstrip("/"))
        if host == base:
            s["endpoint_owner"] = other
            if not os.environ.get("DR_MODEL", "").strip():
                s["default_model"] = op["defaultModel"]
            break
    return s


def select():
    """Which provider this run uses. Pure: reads env, never touches a credential.

    Resolution order is DR_PROVIDER, then one-set-key inference, then the contract
    default. A missing DR_PROVIDER value or an unknown name is refused with the
    valid names listed - a typo must not silently fall through to inference and
    bill a different account than the one asked for.
    """
    explicit = os.environ.get("DR_PROVIDER", "").strip()
    if explicit:
        if explicit not in _CONTRACT["providers"]:
            raise AuthError("DR_PROVIDER=%r is not one of: %s"
                            % (explicit, ", ".join(names())))
        return spec(explicit)
    # Inference: each provider's key environments are disjoint, so the set keys
    # vote. One vote is a decision; two are an ambiguity that must be refused
    # aloud rather than resolved by dict order.
    voted = [(n, [e for e in _CONTRACT["providers"][n]["keyEnvs"]
                  if os.environ.get(e, "").strip()])
             for n in names()]
    voted = [(n, set_envs) for n, set_envs in voted if set_envs]
    if len(voted) == 1:
        return spec(voted[0][0])
    if len(voted) > 1:
        pairs = "; ".join("%s=%s" % (n, ", ".join(envs)) for n, envs in voted)
        raise AuthError(
            "Credentials for more than one provider are set (%s). Set DR_PROVIDER "
            "to one of %s to choose - guessing here would bill the wrong account."
            % (pairs, ", ".join(names())))
    return spec(_CONTRACT["default"])


def _load_key(spec):
    for e in spec["key_envs"]:
        key = os.environ.get(e, "").strip()
        if key:
            # Remember WHICH env supplied it: the "api-key" scheme is the same,
            # but preflight's message should name the variable the user set.
            return "api-key", key, e
    return None


def _load_oauth(spec):
    """The Claude Code login fallback. Exists only for providers that declare it.

    Byte-for-byte the logic engine.py shipped from the start: expand the declared
    paths (``~`` and ``$HERMES_HOME``), read ``claudeAiOauth.accessToken``, refuse
    an expired token with the expiry in local time rather than a mystery 401.
    """
    o = spec["oauth"] or {}
    tried = []
    for raw in o.get("credPaths", []):
        # $HERMES_HOME expands to the env var when set, /opt/data when not - the
        # same default engine.py carried from its first day.
        p = os.path.expanduser(raw.replace("$HERMES_HOME",
                                           os.environ.get("HERMES_HOME", "/opt/data")))
        tried.append(p)
        try:
            with open(p) as f:
                d = json.load(f)
        except Exception:
            continue
        tok = (d.get("claudeAiOauth") or {}).get("accessToken")
        if tok:
            exp = (d.get("claudeAiOauth") or {}).get("expiresAt")
            if exp and exp / 1000.0 < time.time():
                raise AuthError("Local Claude Code credential expired at %s. Set %s instead."
                                % (time.strftime("%Y-%m-%d %H:%M",
                                                 time.localtime(exp / 1000.0)),
                                  spec["key_env"]))
            return "oauth", tok, None
    raise AuthError(
        "No credentials for %s. Set %s (%s). Looked for a local Claude Code "
        "credential in: %s"
        % (spec["label"], spec["key_env"], spec["key_help"] or "see the provider's console",
           ", ".join(tried) if tried else "(this provider declares no login file)"))


def credential(spec=None):
    """(scheme, secret, env_that_supplied_it) for the selected provider.

    The third element lets preflight say "the credential loaded (api-key via
    ZAI_API_KEY)" - naming the variable the user actually set rather than the
    contract's first-listed one.
    """
    spec = spec or select()
    got = _load_key(spec)
    if got:
        return got
    if spec["oauth"]:
        return _load_oauth(spec)
    raise AuthError("No credentials for %s. Set %s (%s)."
                    % (spec["label"], spec["key_env"], spec["key_help"] or "see the provider's console"))


def _oauth_headers(spec, secret):
    o = spec["oauth"]
    version = os.environ.get(o["versionEnv"], o["defaultVersion"])
    return {
        "authorization": "Bearer " + secret,
        "anthropic-beta": o["betas"],
        "user-agent": o["userAgent"].replace("{version}", version),
        "x-app": "cli",
    }


# Memoised because credential() reads files (the OAuth login) and the engine calls
# the transport head once per agent call, ~150 times a run.
_TRANSPORT, _lock = None, threading.Lock()


def transport():
    """Everything agent()'s request head needs, behind one call.

    Returns the Spec fields plus the resolved scheme/secret and the fully
    assembled header dict. The system PREFIX is the provider's identity block;
    the worker instruction block after it is engine-owned and provider-agnostic.
    """
    global _TRANSPORT
    with _lock:
        if _TRANSPORT is None:
            spec = select()
            # Session-first (ADR-0005): when the harness CLI that powers this provider
            # exists on the machine, IT is the power source and no credential is read
            # at all - the whole point is a run that holds no API key. Only the HTTP
            # fallback resolves a credential, so a session-powered describe() can
            # never misname a key nobody set.
            argv = harness_command(spec)
            if argv is not None:
                _TRANSPORT = dict(spec, scheme="session", secret=None, via=None,
                                  headers=None, harness_argv=argv)
                return _TRANSPORT
            scheme, secret, via = credential(spec)
            headers = {"content-type": "application/json", **spec["static_headers"]}
            if scheme == "api-key":
                headers["x-api-key"] = secret
            else:
                headers.update(_oauth_headers(spec, secret))
            _TRANSPORT = dict(spec, scheme=scheme, secret=secret, via=via, headers=headers)
        return _TRANSPORT


def reset():
    """Forget the memoised transport. For tests that mutate the environment."""
    global _TRANSPORT
    with _lock:
        _TRANSPORT = None


def describe():
    """One line for --selftest and preflight: who we are calling and how.

    The endpoint-owner suffix exists because of the env-shim case: a gateway mapping
    a Z.ai key into ANTHROPIC_* made this line read "Anthropic (api-key)" while every
    call went to api.z.ai. The line is what an agent reads mid-failure; it must not
    mis-describe the wire.
    """
    t = transport()
    if t.get("scheme") == "session":
        return "%s (session via %s - login-powered, no API key)" % (t["label"], t["harness"]["label"])
    via = "via " + t["via"] if t.get("via") else ""
    owner = ("; endpoint is %s's (%s override) - model default follows the endpoint"
             % (_CONTRACT["providers"][t["endpoint_owner"]]["label"],
                _CONTRACT["providers"][t["name"]]["baseUrlEnv"])
             ) if t.get("endpoint_owner") else ""
    return "%s (%s%s)%s" % (t["label"], t["scheme"], ", " + via if via else "", owner)
