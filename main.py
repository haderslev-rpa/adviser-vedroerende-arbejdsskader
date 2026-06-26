import asyncio
import logging
import sys
from dotenv import load_dotenv

load_dotenv()

from behandel import behandel_page
from hent_adviser_fra_sapa import hent_adviser
from pprint import pprint

from q_haderslev_vbo.playwright.browser_session import BrowserSession
from automation_server_client import (
    AutomationServer,
    Workqueue,
    WorkItemError,
    WorkItemStatus
)

from q_haderslev_vbo.automation_server.ats_update_item_data import update_item_data


# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("automation_server_client").setLevel(logging.WARNING)
logging.getLogger("debugpy").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# QUEUE-MODE
# ---------------------------------------------------------------------------
async def populate_queue(workqueue: Workqueue, debug: bool):

    logger = logging.getLogger(__name__)
    logger.info("Populate queue mode started")

    print("🔄 Starter hentning af adviser...")

    session = BrowserSession(headless=True, debug=debug)
    await session.start()
    page = await session.new_page()

    try:
        adviser = await hent_adviser(session=session, page=page)

        for advis in adviser:
            data_json = {}

            update_item_data(
                data_json,
                box_updates=advis,
                update=False
            )

            workqueue.add_item(
                data=data_json,
                reference=data_json["box"]["cpr"]
            )

        logger.info(f"{len(adviser)} items tilføjet til workqueue")

    finally:
        await session.close()


# ---------------------------------------------------------------------------
# PROCESS-MODE
# ---------------------------------------------------------------------------
async def process_workqueue(workqueue: Workqueue, debug: bool):

    logger = logging.getLogger(__name__)
    logger.info(f"Process workqueue mode started (debug={debug})")

    session = BrowserSession(headless=True, debug=debug)
    await session.start()

    try:
        for item in workqueue:

            with item:
                data = item.data

                # ✅ Ny page for hvert item
                page = await session.new_page()

                try:
                    print("\n==================================== NEXT ITEM ====================================")
                    pprint(data)

                    await behandel_page(
                        item=item,
                        session=session,
                        page=page
                    )

                    update_item_data(
                        data,
                        status="Completed",
                        status_code="Advis færdiggjort",
                        item=item
                    )

                    item.update(data)
                    item.complete("Completed")

                    await session.close_other_pages(page)

                except WorkItemError as e:
                    logger.error(f"WorkItemError for item {item.reference}: {e}")
                    item.fail(str(e))

                    # Restart browser
                    await session.close()
                    session = BrowserSession(headless=True, debug=debug)
                    await session.start()

                except Exception as e:
                    logger.exception("Uventet fejl")

                    try:
                        if session.context and session.context.pages:
                            page = session.context.pages[-1]
                            await session.screenshot(
                                page,
                                f"hard_exception_{type(e).__name__}",
                                always=True
                            )
                    except Exception:
                        logger.warning("Kunne ikke tage screenshot ved hard error")

                    await session.close()
                    raise

    finally:
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
        workqueue.clear_workqueue(WorkItemStatus.NEW)
        asyncio.run(populate_queue(workqueue, debug=DEBUG))
        sys.exit(0)

    asyncio.run(process_workqueue(workqueue, debug=DEBUG))