import asyncio
import logging
import sys
import os

# ✅ Load .env
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
# SETUP BROWSER SESSION
# ---------------------------------------------------------------------------
browser: BrowserSession = BrowserSession(headless=True)


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
# QUEUE-MODE (PRODUCER)
# ---------------------------------------------------------------------------
async def populate_queue(workqueue: Workqueue, page=None):
    logger = logging.getLogger(__name__)
    logger.info("Populate queue mode started")

    print("🔄 Starter hentning af adviser...")

    adviser = await hent_adviser(page)

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


# ---------------------------------------------------------------------------
# PROCESS-MODE (WORKER)
# ---------------------------------------------------------------------------
async def process_workqueue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)
    logger.info("Process workqueue mode started")

    # ✅ FIX: start browser session
    await browser.start()

    page = None  # ✅ vigtig initialisering

    for item in workqueue:
        with item:
            data = item.data

            try:
                print("==================================== NEXT ITEM ====================================")
                pprint(item.data)

                # ✅ hent/genbrug page
                page = await browser.ensure_page_alive(page)

                # ✅ send page med
                await behandel_page(item, page)

                update_item_data(
                    data,
                    item=item,
                    status_updates={
                        "status": "Manuel",
                        "status_kode": "BORGER_UDENFOR_SCOPE"
                    },
                )

                status_dict = data.get("status", {})

                if isinstance(status_dict, dict):
                    message = status_dict.get("status", "Completed")
                else:
                    message = "Completed"

                item.complete(message)

            except WorkItemError as e:
                logger.error(f"WorkItemError for item {item.reference}: {e}")
                item.fail(str(e))

            except Exception:
                logger.exception("Uventet fejl")
                raise

    # ✅ luk browser til sidst
    await browser.close()


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ats = AutomationServer.from_environment()
    workqueue = ats.workqueue()

    # -----------------------------------------------------------------------
    # QUEUE-MODE
    # -----------------------------------------------------------------------
    if "--queue" in sys.argv:

        workqueue.clear_workqueue(WorkItemStatus.NEW)

        asyncio.run(populate_queue(workqueue))
        sys.exit(0)

    # -----------------------------------------------------------------------
    # PROCESS-MODE
    # -----------------------------------------------------------------------
    asyncio.run(process_workqueue(workqueue))
