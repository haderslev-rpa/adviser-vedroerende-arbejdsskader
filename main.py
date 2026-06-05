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
from q_sapa.launch import launch_sapa
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
async def populate_queue(workqueue: Workqueue, debug: bool):
    logger = logging.getLogger(__name__)
    logger.info("Populate queue mode started")

    print("🔄 Starter hentning af adviser...")
    session = BrowserSession(headless=True,debug=debug)
    await session.start()

    page = await session.new_page()  # Page (browser-fane)
    
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


async def process_workqueue(workqueue: Workqueue, debug: bool):
    logger = logging.getLogger(__name__)
    logger.info(f"Process workqueue mode started (debug={debug})")

    # =========================================================
    # 🌐 PLAYWRIGHT – ÉN BROWSERSESSION FOR HELE PROCESSEN
    #
    # ✅ KAN SLETTES i processer uden browser
    # =========================================================
    session = BrowserSession(headless=True,debug=debug)
    await session.start()
    page = await session.new_page()  # Page (browser-fane)

    try: # denne try bruges kun til PLAYWRIGHT processer
        # Workqueue er iterable → hvert item behandles ét ad gangen
        for item in workqueue:

            with item:
                data = item.data

                try:
                    print("==================================== NEXT ITEM ====================================")
                    pprint(data)

                    # --------------------------------------------------
                    # ▶ PROCESS-KODE
                    # (behandel_page bruger Playwright internt)
                    # --------------------------------------------------
                    await behandel_page(item=item, session=session, page=page) #Fjern session og page hvis du ikke bruger Playwright i din process

                    #update_item_data er din egen funktion som du kan bruge til at opdatere item data og logge samtidig. Den er typisk nyttig i process
                    update_item_data(
                        data,
                        status="Completed",
                        status_code="Advis færdiggjort",
                        item=item 
                    )

                    item.update(data)
                    item.complete("Completed")

                except WorkItemError as e:
                    # =================================================
                    # ✅ SOFT ERROR
                    # - Item fejler
                    # =================================================
                    logger.error(f"WorkItemError for item {item.reference}: {e}")
                    item.fail(str(e))
                    
                    # Playwright:
                    # Luk browser for sikkerhed (ny session på næste item)
                    session = BrowserSession(headless=True,debug=debug)
                    await session.start()

                except Exception:
                    # =================================================
                    # ❌ HARD ERROR
                    # - Screenshot tages
                    # - Browser lukkes
                    # - Processen STOPPER
                    # =================================================
                    logger.exception("Uventet fejl")

                    try: #Playwright:
                        if session.context and session.context.pages:
                            page = session.context.pages[-1]
                            await session.recorder.screenshot(
                                page,
                                "hard_exception",
                                always=True
                            )
                    except Exception:
                        logger.warning("Kunne ikke tage screenshot ved hard error")

                    # Luk ALT (Playwright)
                    await session.close()

                    # Stop hele processen (Automation Server genstarter)
                    raise

    finally: # PLAYWRIGHT:
        # =====================================================
        # 🧹 SIKKER OPRYDNING
        #
        # ✅ Lukker browser hvis processen afsluttes normalt
        # =====================================================
        await session.close() # denne try bruges kun til PLAYWRIGHT processer og kan slettes



# ------------------------------------------------------------
# MAIN ENTRY POINT
# ------------------------------------------------------------
if __name__ == "__main__":

    # ✅ CLI flags (runtime-parametre)
    DEBUG = "--debug" in sys.argv   # bool (sand/falsk)
    QUEUE_MODE = "--queue" in sys.argv

    ats = AutomationServer.from_environment()
    workqueue = ats.workqueue()

    # --------------------------------------------------------
    # QUEUE-MODE
    # --------------------------------------------------------
    if QUEUE_MODE:
        # ---------------------------------------------------------------
        # VIGTIGT:
        # Denne linje CLEARSER alle NEW items i køen.
        #
        # ❗ Hvis du ALDRIG vil slette eksisterende NEW items:
        #     → så SKAL denne linje fjernes eller kommenteres ud.
        #
        # workqueue.clear_workqueue(WorkItemStatus.NEW)
        
        workqueue.clear_workqueue(WorkItemStatus.NEW)
        asyncio.run(populate_queue(workqueue, debug=DEBUG))
        sys.exit(0)

    # --------------------------------------------------------
    # PROCESS-MODE
    # --------------------------------------------------------
    asyncio.run(process_workqueue(workqueue, debug=DEBUG))