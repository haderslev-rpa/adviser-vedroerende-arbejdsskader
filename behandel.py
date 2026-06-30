async def behandel_page(item, page, session):

    from q_haderslev_vbo.automation_server.ats_update_item_data import update_item_data
    from q_haderslev_vbo.automation_server.ats_find_state import find_state

    from q_fasit.functionality.launch import launch_fasit
    from q_fasit.functionality.fremsoeg_borger import fremsoeg_borger
    from q_fasit.functionality.borgeroverblik import bo_kommunens_markeringer

    from q_sapa.functionality import advis_marker_faerdiggjort

    import logging
    logger = logging.getLogger(__name__)

    data = item.data

    # ==========================================================
    # 🧠 STATES (konstanter → faste værdier)
    # ==========================================================
    class States:
        FREMSOEGT_BORGER = "1.0 Fremsøgt borger og gemt advis i Fasit"
        SAPA_FAERDIG = "2.0 Advis markeret færdiggjort i SAPA"

    # ==========================================================
    # 🔁 HELPERS (hjælpefunktioner → små værktøjer)
    # ==========================================================
    def mangler_state(state, step):
        states = data.get("state", [])

        match = next((s for s in states if state in s), None)

        if match:
            log_step(step, f'Skip "{match}"')
            return False

        return True

    def set_state(state):
        # ✅ ét kald (bedre)
        update_item_data(data, item=item, state=state)

    def log_step(step, text):
        logger.info(f"[{step}] {text}")

    # ==========================================================
    # ✅ STEP 1 – FASIT
    # ==========================================================
    step = "FREMSOEGT_BORGER"
    state = getattr(States, step)

    if mangler_state(state, step):

        log_step(step, "Starter FASIT")

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

        await bo_kommunens_markeringer(
            page=page,
            session=session,
            tekst=note_tekst,
        )

        set_state(state)

    # ==========================================================
    # ✅ STEP 2 – SAPA
    # ==========================================================
    step = "SAPA_FAERDIG"
    state = getattr(States, step)

    if mangler_state(state, step):

        log_step(step, "Starter SAPA")

        url = data["box"]["url_til_advis"]

        await advis_marker_faerdiggjort(
            page=page,
            session=session,
            url_til_advis=url
        )

        set_state(state)
