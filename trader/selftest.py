"""`--selftest`: checks .env keys, Alpaca connectivity, Robinhood MCP
connection+auth, and Anthropic API reachability. Prints a PASS/FAIL table
and returns 0 only if every check passes (non-zero otherwise, per the
`config/auth error` exit code convention)."""

from __future__ import annotations

from dataclasses import dataclass

from trader.config import Config, ConfigError, Secrets


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def _check_env(secrets_or_error: Secrets | ConfigError) -> CheckResult:
    if isinstance(secrets_or_error, ConfigError):
        return CheckResult(".env secrets", False, str(secrets_or_error))
    return CheckResult(".env secrets", True, "ALPACA_KEY, ALPACA_SECRET, ANTHROPIC_API_KEY present")


def _check_config(config_or_error: Config | ConfigError) -> CheckResult:
    if isinstance(config_or_error, ConfigError):
        return CheckResult("config.yaml", False, str(config_or_error))
    return CheckResult("config.yaml", True, f"mode={config_or_error.mode}")


def _check_alpaca(secrets: Secrets) -> CheckResult:
    try:
        from trader.alpaca_data import AlpacaData, AlpacaDataError

        alpaca = AlpacaData(secrets.alpaca_key, secrets.alpaca_secret, paper=True)
        alpaca.get_account_equity_check()
        return CheckResult("Alpaca connectivity", True, "clock endpoint reachable")
    except Exception as exc:  # noqa: BLE001
        return CheckResult("Alpaca connectivity", False, str(exc))


def _check_robinhood_mcp() -> CheckResult:
    try:
        from trader.mcp_robinhood import RobinhoodMCPClient, discover_robinhood_mcp_server

        spec = discover_robinhood_mcp_server()
        client = RobinhoodMCPClient(spec)
        client.connect(timeout=30.0)
        role_map = dict(client.role_map)
        client.close()
        return CheckResult("Robinhood MCP", True, f"roles mapped: {role_map}")
    except Exception as exc:  # noqa: BLE001
        return CheckResult("Robinhood MCP", False, str(exc))


def _check_anthropic(secrets: Secrets, model: str) -> CheckResult:
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=secrets.anthropic_api_key)
        info = client.models.retrieve(model)
        return CheckResult("Anthropic API", True, f"reachable; model={info.id}")
    except Exception as exc:  # noqa: BLE001
        return CheckResult("Anthropic API", False, str(exc))


def run_selftest() -> int:
    results: list[CheckResult] = []

    try:
        from trader.config import load_config

        config = load_config()
        results.append(_check_config(config))
    except ConfigError as exc:
        results.append(_check_config(exc))
        config = None

    try:
        from trader.config import load_secrets

        secrets = load_secrets()
        results.append(_check_env(secrets))
    except ConfigError as exc:
        results.append(_check_env(exc))
        secrets = None

    if secrets is not None:
        results.append(_check_alpaca(secrets))
        model = config.anthropic.model if config is not None else "claude-sonnet-4-6"
        results.append(_check_anthropic(secrets, model))
    else:
        results.append(CheckResult("Alpaca connectivity", False, "skipped: no secrets"))
        results.append(CheckResult("Anthropic API", False, "skipped: no secrets"))

    results.append(_check_robinhood_mcp())

    _print_table(results)
    return 0 if all(r.passed for r in results) else 3


def _print_table(results: list[CheckResult]) -> None:
    name_width = max(len(r.name) for r in results) + 2
    print("\nQuickStockBot --selftest")
    print("-" * (name_width + 60))
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"{r.name:<{name_width}} {status:<6} {r.detail}")
    print("-" * (name_width + 60))
    overall = "PASS" if all(r.passed for r in results) else "FAIL"
    print(f"Overall: {overall}\n")
