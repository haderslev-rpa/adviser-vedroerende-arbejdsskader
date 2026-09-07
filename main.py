import asyncio
import logging
import sys
from pprint import pprint

from automation_server_client import (
    AutomationServer,
    WorkItemError,
    WorkItemStatus,
    Workqueue,
)

from behandel import behandel_page
from hent_adviser_fra_sapa import hent_adviser
from q_fasit.api.client import FasitApiClient
from q_fasit.api.token_manager import FasitTokenManager
from q_haderslev_vbo.automation_server.ats_update_item_data import (
    update_item_data,
)
from q_haderslev_vbo.playwright.browser_session import BrowserSession


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# KONFIGURATION
# ---------------------------------------------------------------------------

HEADLESS = True
FASIT_HEADLESS = True

FASIT_CREDENTIAL_NAME = "DIRXOPS"

FASIT_FALLBACK_LIFETIME_SECONDS = 15 * 60
FASIT_EXPIRY_MARGIN_SECONDS = 60


# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s [%(levelname)s] "
        "%(name)s: %(message)s"
    ),
)

logging.getLogger(
    "httpx"
).setLevel(
    logging.WARNING
)

logging.getLogger(
    "automation_server_client"
).setLevel(
    logging.WARNING
)

logging.getLogger(
    "debugpy"
).setLevel(
    logging.WARNING
)


# ---------------------------------------------------------------------------
# QUEUE-MODE
# ---------------------------------------------------------------------------

async def populate_queue(
    workqueue: Workqueue,
    debug: bool,
) -> None:
    """
    Henter adviser fra SAPA og opretter dem som
    elementer i ATS-workqueuen.
    """
    logger.info(
        "Populate queue mode started."
    )

    print(
        "Starter hentning af adviser..."
    )

    session = BrowserSession(
        headless=HEADLESS,
        debug=debug,
    )

    await session.start()

    try:
        page = await session.new_page()

        adviser = await hent_adviser(
            session=session,
            page=page,
        )

        for advis in adviser:
            data_json: dict = {}

            update_item_data(
                data_json,
                box_updates=advis,
                update=False,
            )

            workqueue.add_item(
                data=data_json,
                reference=data_json["box"]["cpr"],
            )

        logger.info(
            "%s items tilføjet til workqueue.",
            len(adviser),
        )

    finally:
        await session.close()


# ---------------------------------------------------------------------------
# PROCESS-MODE
# ---------------------------------------------------------------------------

async def process_workqueue(
    workqueue: Workqueue,
    debug: bool,
) -> None:
    """
    Behandler elementerne i ATS-workqueuen.

    BrowserSession anvendes til SAPA.
    FasitApiClient anvendes til FASIT.
    """
    logger.info(
        "Process workqueue mode started "
        "(debug=%s).",
        debug,
    )

    session = BrowserSession(
        headless=HEADLESS,
        debug=debug,
    )

    fasit_token_manager = FasitTokenManager(
        credential_name=FASIT_CREDENTIAL_NAME,
        headless=FASIT_HEADLESS,
        fallback_lifetime_seconds=(
            FASIT_FALLBACK_LIFETIME_SECONDS
        ),
        expiry_margin_seconds=(
            FASIT_EXPIRY_MARGIN_SECONDS
        ),
    )

    fasit_api_client = FasitApiClient(
        token_manager=fasit_token_manager,
    )

    await session.start()

    try:
        for item in workqueue:
            with item:
                data = item.data
                page = await session.new_page()

                try:
                    print(
                        "\n"
                        "==================================== "
                        "NEXT ITEM "
                        "===================================="
                    )

                    pprint(
                        data
                    )

                    await behandel_page(
                        item=item,
                        session=session,
                        page=page,
                        fasit_api_client=(
                            fasit_api_client
                        ),
                    )

                    update_item_data(
                        data,
                        status="Completed",
                        status_code=(
                            "Advis færdiggjort"
                        ),
                        item=item,
                    )

                    item.update(
                        data
                    )

                    item.complete(
                        "Completed"
                    )

                    await session.close_all_other_tabs(
                        page
                    )

                except WorkItemError as error:
                    logger.error(
                        "WorkItemError for item %s: %s",
                        item.reference,
                        error,
                    )

                    item.fail(
                        str(error)
                    )

                    await session.close()

                    session = BrowserSession(
                        headless=HEADLESS,
                        debug=debug,
                    )

                    await session.start()

                except Exception as error:
                    logger.exception(
                        "Uventet fejl for item %s.",
                        item.reference,
                    )

                    try:
                        if (
                            session.context
                            and session.context.pages
                        ):
                            error_page = (
                                session.context.pages[-1]
                            )

                            await session.screenshot(
                                error_page,
                                (
                                    "hard_exception_"
                                    f"{type(error).__name__}"
                                ),
                                always=True,
                            )

                    except Exception:
                        logger.warning(
                            "Kunne ikke tage screenshot "
                            "ved hard error."
                        )

                    await session.close()

                    raise

    finally:
        await fasit_api_client.close()
        await fasit_token_manager.close()
        await session.close()


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Starter processen i queue-mode eller process-mode.

    Kommandolinjeflag:
    - --debug: Aktiverer debug-mode.
    - --queue: Henter adviser og udfylder workqueuen.
    """
    debug = "--debug" in sys.argv
    queue_mode = "--queue" in sys.argv

    logger.info(
        "Starter proces. "
        "queue_mode=%s, debug=%s, "
        "headless=%s, fasit_headless=%s.",
        queue_mode,
        debug,
        HEADLESS,
        FASIT_HEADLESS,
    )

    ats = AutomationServer.from_environment()
    workqueue = ats.workqueue()

    if queue_mode:
        workqueue.clear_workqueue(
            WorkItemStatus.NEW
        )

        asyncio.run(
            populate_queue(
                workqueue=workqueue,
                debug=debug,
            )
        )

        return

    asyncio.run(
        process_workqueue(
            workqueue=workqueue,
            debug=debug,
        )
    )


if __name__ == "__main__":
    main()
