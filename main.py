import asyncio
import logging
import sys
from behandel import behandel_page

from pprint import pprint #Fjernes efter brug hjælper med printing af data i et læsbart format

# Automation Server klienten
from automation_server_client import (AutomationServer, Workqueue, WorkItemError, WorkItemStatus)
from q_haderslev_vbo.automation_server.ats_update_item_data import update_item_data

# ---------------------------------------------------------------------------
# LOGGING
# Skabelonerne forventer, at logging er sat op tidligt
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
#
# Denne funktion køres KUN når scriptet startes med --queue
# Den må:
#   ✅ oprette testdata
#   ✅ kalde update_item_data
#   ✅ tilføje items til køen
# Den må IKKE:
#   ❌ behandle items
#   ❌ complete/fail items
# ---------------------------------------------------------------------------
async def populate_queue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)
    logger.info("Populate queue mode started")

    # -----------------------------------------------------------------------
    # EKSEMPEL: FIKTIVE TESTDATA (det er her dine test-items hører til)
    # Disse data kan komme fra:
    #   - Excel
    #   - CSV
    #   - API
    #   - Test-hardcodet data (som her)
    # -----------------------------------------------------------------------
    raw_items = [
        {"cpr": "1234567891", "type": "adresseopslag", "note": "Test-item 1"},
        {"cpr": "1111111111", "type": "fødselsdato-check", "note": "Test-item 2"},
        {"cpr": "2222222222", "type": "myndighedsopslag", "note": "Test-item 3"},
        {"cpr": "3333333333", "type": "journalopslag", "note": "Test-item 4"},
    ]

    # -----------------------------------------------------------------------
    # Her standardiserer vi data
    # -----------------------------------------------------------------------
    for raw_item in raw_items:
        data_json = {}

        # Her bliver flad input-data konverteret til korrekt item-struktur
        update_item_data(
            data_json,
            box_updates=raw_item,
            update=False
        )

        # -------------------------------------------------------------------
        # Tilføj item til queue
        # reference bruges typisk til sporbarhed (fx CPR, sagsnr osv.) ret derfor nedenstående "cpr" til det der skal vises i ATS UI'et
        # -------------------------------------------------------------------
        workqueue.add_item(
            data=data_json,
            reference=data_json["box"]["cpr"]
        )

    logger.info(f"{len(raw_items)} items tilføjet til workqueue")


# ---------------------------------------------------------------------------
# PROCESS-MODE (WORKER)
#
# Denne funktion køres når scriptet startes UDEN --queue
# Den må:
#   ✅ læse items fra køen
#   ✅ behandle data
#   ✅ complete/fail items
# Den må IKKE:
#   ❌ oprette testdata
#   ❌ tilføje items til køen
# ---------------------------------------------------------------------------
async def process_workqueue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)
    logger.info("Process workqueue mode started")

    # Workqueue er iterable → hvert item tages ét ad gangen
    for item in workqueue:

        # with item:
        #   - låser item
        #   - hvis der ikke kaldes complete/fail → rollbackes item
 
        with item:
            data = item.data  # dict (deserialiseret JSON)

            try:

                print("==================================== NEXT ITEM ==================================== ")
                pprint(item.data)

                # --- Indsæt din proceskode her --- eller brug behandel_page
                behandel_page(item) #Filen behandl.py



                #update_item_data er funktion som du kan bruge til at opdatere item data. Den er typisk nyttig i process og bruges ofte på behandel page
                update_item_data(
                    data,
                    item=item
                    status_updates={
                        "status": "Manuel",
                        "status_kode": "BORGER_UDENFOR_SCOPE" 
                    },
                )            

                # status ligger i data["status"],
                status_dict = data.get("status", {})

                if isinstance(status_dict, dict):
                    message = status_dict.get("status", "Completed")
                else:
                    message = "Completed"

                item.complete(message)



            except WorkItemError as e:
                # Soft error:
                logger.error(f"WorkItemError for item {item.reference}: {e}")
                item.fail(str(e))

            except Exception as e:
                # Hard error:
                # Brug evt. raise hvis processen skal stoppe
                logger.exception("Uventet fejl")
                raise


# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Automation Server konfiguration læses fra miljøet:
    # ATS_URL, ATS_TOKEN, ATS_WORKQUEUE osv.
    ats = AutomationServer.from_environment()
    workqueue = ats.workqueue()

    # -----------------------------------------------------------------------
    # QUEUE-MODE
    # -----------------------------------------------------------------------
    if "--queue" in sys.argv:

        # ---------------------------------------------------------------
        # VIGTIGT:
        # Denne linje CLEARSER alle NEW items i køen.
        #
        # ❗ Hvis du ALDRIG vil slette eksisterende NEW items:
        #     → så SKAL denne linje fjernes eller kommenteres ud.
        #
        # workqueue.clear_workqueue(WorkItemStatus.NEW)
        # ---------------------------------------------------------------
        workqueue.clear_workqueue(WorkItemStatus.NEW)

        asyncio.run(populate_queue(workqueue))
        sys.exit(0)

    # -----------------------------------------------------------------------
    # PROCESS-MODE (standard)
    # -----------------------------------------------------------------------
    asyncio.run(process_workqueue(workqueue))
