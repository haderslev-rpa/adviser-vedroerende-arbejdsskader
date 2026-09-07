import asyncio
import logging
import os
import sys
from pprint import pprint

from dotenv import load_dotenv

load_dotenv()

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


def get_headless_flag() -> bool:
    """
    Læser HEADLESS fra .env.

    Skriv HEADLESS=false for at se browseren under kørsel.
    """
    return os.getenv(
        "HEADLESS",
        "true",
    ).strip().lower() == "true"


def get_fasit_headless_flag() -> bool:
    """
    Læser FASIT_HEADLESS fra .env.

    Hvis FASIT_HEADLESS ikke er angivet, genbruges HEADLESS.
    """
    default_value = (
        "true"
        if get_headless_flag()
        else "false"
    )

    return os.getenv(
        "FASIT_HEADLESS",
        default_value,
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "ja",
    }


# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("automation_server_client").setLevel(logging.WARNING)
logging.getLogger("debugpy").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# QUEUE-MODE
# ---------------------------------------------------------------------------

async def populate_queue(
    workqueue: Workqueue,
    debug: bool,
) -> None:
    logger.info("Populate queue mode started")
    print("Starter hentning af adviser...")

    headless = get_headless_flag()
    session = BrowserSession(
        headless=headless,
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
            "%s items tilføjet til workqueue",
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
    logger.info(
        "Process workqueue mode started (debug=%s)",
        debug,
    )

    headless = get_headless_flag()

    session = BrowserSession(
        headless=headless,
        debug=debug,
    )

    fasit_token_manager = FasitTokenManager(
        credential_name="DIRXOPS",
        headless=get_fasit_headless_flag(),
        fallback_lifetime_seconds=15 * 60,
        expiry_margin_seconds=60,
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
                        "\n==================================== "
                        "NEXT ITEM "
                        "===================================="
                    )
                    pprint(data)

                    await behandel_page(
                        item=item,
                        session=session,
                        page=page,
                        fasit_api_client=fasit_api_client,
                    )

                    update_item_data(
                        data,
                        status="Completed",
                        status_code="Advis færdiggjort",
                        item=item,
                    )

                    item.update(data)
                    item.complete("Completed")

                    await session.close_all_other_tabs(page)

                except WorkItemError as error:
                    logger.error(
                        "WorkItemError for item %s: %s",
                        item.reference,
                        error,
                    )

                    item.fail(str(error))

                    await session.close()

                    session = BrowserSession(
                        headless=headless,
                        debug=debug,
                    )
                    await session.start()

                except Exception as error:
                    logger.exception(
                        "Uventet fejl for item %s",
                        item.reference,
                    )

                    try:
                        if (
                            session.context
                            and session.context.pages
                        ):
                            error_page = session.context.pages[-1]

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
                            "Kunne ikke tage screenshot ved hard error"
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

if __name__ == "__main__":
    DEBUG = "--debug" in sys.argv
    QUEUE_MODE = "--queue" in sys.argv

    ats = AutomationServer.from_environment()
    workqueue = ats.workqueue()

    if QUEUE_MODE:
        workqueue.clear_workqueue(
            WorkItemStatus.NEW
        )

        asyncio.run(
            populate_queue(
                workqueue,
                debug=DEBUG,
            )
        )
        sys.exit(0)

    asyncio.run(
        process_workqueue(
            workqueue,
            debug=DEBUG,
        )
    )
