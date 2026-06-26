async def behandel_page(item, page, session):

    from q_haderslev_vbo.automation_server.ats_update_item_data import update_item_data
    from q_haderslev_vbo.automation_server.ats_find_state import find_state

    from q_fasit.functionality.launch import launch_fasit
    from q_fasit.functionality.fremsoeg_borger import fremsoeg_borger
    from q_fasit.functionality.bo_kommunens_markeringer import bo_kommunens_markeringer

    from q_sapa.functionality import advis_marker_faerdiggjort

    import logging
    logger = logging.getLogger(__name__)

    data = item.data

    class States:
        FREMSOEGT_BORGER = "1.0 Fremsøgt borger og gemt advis i Fasit"
        SAPA_FAERDIG = "2.0 Advis markeret færdiggjort i SAPA"

    def har_state(state):
        return find_state(data, search_text=state)

    def mangler_state(state):
        return not har_state(state)

    def set_state(state):
        update_item_data(data, item=item, state=state)

    def log_step(step, text):
        logger.info(f"[{step}] {text}")

    # ==========================================================
    # ✅ STEP 1 – FASIT
    # ==========================================================
    state = States.FREMSOEGT_BORGER

    if mangler_state(state):

        log_step(state, "Starter FASIT")

        cpr = data["box"]["cpr"]
        tekst = data["box"]["haendelse"]
        dato = data["box"]["dato"]

        note_tekst = f"{dato} - {tekst}"

        await launch_fasit(page=page, session=session, credential_name="DIRXOPS")

        page = await fremsoeg_borger(
            page=page,
            session=session,
            cpr=cpr
        )

        print("✅ Aktiv page efter fremsoeg:", page.url)
        print("Page lukket?", page.is_closed())

        await bo_kommunens_markeringer(
            page=page,
            session=session,
            tekst=note_tekst,
        )

        data["box"]["journal_id"] = "FASIT_OK"
        update_item_data(data, item=item)
        set_state(state)

    # ==========================================================
    # ✅ STEP 2 – SAPA
    # ==========================================================
    state = States.SAPA_FAERDIG

    if mangler_state(state):

        log_step(state, "Starter SAPA")

        url = data["box"]["url_til_advis"]

        await advis_marker_faerdiggjort(
            page=page,
            session=session,
            url_til_advis=url
        )

        data["box"]["afslutnings_id"] = "SAPA_OK"
        update_item_data(data, item=item)
        set_state(state)