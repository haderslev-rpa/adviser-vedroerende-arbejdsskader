import asyncio
import logging
import sys
from behandel import behandel_page
from hent_adviser_fra_sapa import hent_adviser

from pprint import pprint

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
# QUEUE-MODE (PRODUCER)
# ---------------------------------------------------------------------------
async def populate_queue(workqueue: Workqueue, page):
    logger = logging.getLogger(__name__)
    logger.info("Populate queue mode started")

    adviser = await hent_adviser(page)

    for raw_item in adviser:
        data_json = {}

        update_item_data(
            data_json,
            box_updates=raw_item,
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

    for item in workqueue:
        with item:
            data = item.data

            try:
                print("==================================== NEXT ITEM ====================================")
                pprint(item.data)

                # Din proces
                behandel_page(item)

                # ✅ FIX: manglende komma tilføjet
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


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ats = AutomationServer.from_environment()
    workqueue = ats.workqueue()

    if "--queue" in sys.argv:
        workqueue.clear_workqueue(WorkItemStatus.NEW)

        # ⚠️ Hvis du ikke har 'page', skal du oprette den her
from q_sapa import launch

async def run_queue():
    browser, page = await launch()

    try:
        await populate_queue(workqueue, page)
    finally:
        await browser.close()


        asyncio.run(run_queue())
        sys.exit(0)

    asyncio.run(process_workqueue(workqueue))
