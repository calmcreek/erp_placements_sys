"""Run exactly one IIT KGP ERP monitoring cycle.

This file is the GitHub Actions entry point. It intentionally does not
start a Flask server or a background loop.
"""

from monitor import (
    authenticate_erp,
    run_monitor_cycle,
    save_dashboard_data,
    update_dashboard,
    validate_environment,
)


def main():
    print("=" * 60)
    print("IIT KGP ERP MONITOR - SINGLE RUN")
    print("=" * 60)

    try:
        validate_environment()
        authenticate_erp()
        run_monitor_cycle()

    except Exception as error:
        print()
        print("Monitor run failed:", str(error))

        update_dashboard(
            erp_status="Error",
            last_error=str(error),
            next_check=None,
        )
        save_dashboard_data()
        raise


if __name__ == "__main__":
    main()
