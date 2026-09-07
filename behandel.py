import logging
from typing import Any

from q_fasit.api.borger import (
    hent_borger_id,
    opret_kommunens_markeringer,
)
from q_fasit.api.client import FasitApiClient
from q_haderslev_vbo.automation_server.ats_find_state import find_state
from q_haderslev_vbo.automation_server.ats_update_item_data import (
    update_item_data,
)
from q_sapa.functionality import advis_marker_faerdiggjort


logger = logging.getLogger(__name__)


async def behandel_page(
    item: Any,
    page: Any,
    session: Any,
    fasit_api_client: FasitApiClient,
) -> None:
    """
    Behandler ét advis.

    FASIT-delen bruger API-klienten. Token-manageren bag klienten
    launcher automatisk FASIT ved første API-kald og genbruger
    tokenet, så længe tokenet er gyldigt.
    """
    data = item.data

    class States:
        FREMSOEGT_BORGER = (
            "1.0 Fremsøgt borger og gemt advis i Fasit"
        )
        SAPA_FAERDIG = (
            "2.0 Advis markeret færdiggjort i SAPA"
        )

    def mangler_state(state: str, step: str) -> bool:
        states = data.get("state", [])
        match = next(
            (
                existing_state
                for existing_state in states
                if state in existing_state
            ),
            None,
        )

        if match:
            log_step(step, f'Skip "{match}"')
            return False

        return True

    def set_state(state: str) -> None:
        update_item_data(
            data,
            item=item,
            state=state,
        )

    def log_step(step: str, text: str) -> None:
        logger.info("[%s] %s", step, text)

    # ==========================================================
    # STEP 1 - FASIT
    # ==========================================================
    step = "FREMSOEGT_BORGER"
    state = getattr(States, step)

    if mangler_state(state, step):
        log_step(
            step,
            "Starter FASIT API og opdaterer Kommunens markeringer",
        )

        cpr = data["box"]["cpr"]
        tekst = data["box"]["haendelse"]
        dato = data["box"]["dato"]
        note_tekst = f"{dato} - {tekst}"

        citizen_id = await hent_borger_id(
            api_client=fasit_api_client,
            cpr=cpr,
        )

        result = await opret_kommunens_markeringer(
            api_client=fasit_api_client,
            citizen_id=citizen_id,
            tekst=note_tekst,
            kun_laes=False,
        )

        if result.get("updated") is True:
            log_step(
                step,
                "Kommunens markeringer blev opdateret via FASIT API",
            )
        else:
            reason = result.get(
                "reason",
                "Feltet indeholdt allerede den ønskede værdi",
            )
            log_step(
                step,
                f"Kommunens markeringer blev ikke ændret: {reason}",
            )

        set_state(state)

    # ==========================================================
    # STEP 2 - SAPA
    # ==========================================================
    step = "SAPA_FAERDIG"
    state = getattr(States, step)

    if mangler_state(state, step):
        log_step(step, "Starter SAPA")

        url = data["box"]["url_til_advis"]

        await advis_marker_faerdiggjort(
            page=page,
            session=session,
            url_til_advis=url,
        )

        set_state(state)
