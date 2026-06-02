def behandel_page(item):

    from q_haderslev_vbo.automation_server.ats_update_item_data import update_item_data
    from q_haderslev_vbo.automation_server.ats_find_state import find_state
    import logging
    logger = logging.getLogger(__name__)
    from q_sapa import launch as sapa_launch, advis_marker_faerdiggjort
    from q_fasit import launch as fasit_launch, fremsoeg_borger, borgeroverblik

    data = item.data

    # ==========================================================
    # 🧠 STATES
    # ==========================================================
    class States:
        HENTET_ADVISER = "1.0 Hentet adviser fra SAPA"
        JOURNALISER_BREV = "2.0 Fremsøgt borger og gemt advis i Fasit"
        MARKERET_FAERDIGGJORT = "3.0 Advis markeret færdiggjort i SAPA"


    # ==========================================================
    # 🔁 HELPERS
    # ==========================================================
    def har_state(state):
        return find_state(data, search_text=state)

    def mangler_state(state):
        return not har_state(state)

    def set_state(state):
        update_item_data(data, item=item, state=state)

    def log_step(step, text):
        logger.info(f"[{step}] {text}")


    # ==========================================================
    step = "HENTET_ADVISER"
    # ==========================================================
    state = getattr(States, step)

    if mangler_state(state):

        log_step(step, "Start")

        data["box"]["brev_sendt_id"] = 123
        log_step(step, f'ID sat: {data["box"]["brev_sendt_id"]}')

        
        update_item_data(data, item=item)

        set_state(state)


    # ==========================================================
    step = "2.0 Fremsøgt borger og gemt advis i Fasit"
    # ==========================================================
    state = getattr(States, step)

    if mangler_state(state):

        log_step(step, "Start")

        data["box"]["journal_id"] = 456
        log_step(step, f'ID sat: {data["box"]["journal_id"]}')

        update_item_data(data, item=item)

        set_state(state)


    # ==========================================================
    step = "3.0 Advis markeret færdiggjort i SAPA"
    # ==========================================================
    state = getattr(States, step)

    if mangler_state(state):

        log_step(step, "Start")

        data["box"]["afslutnings_id"] = 789
        log_step(step, f'ID sat: {data["box"]["afslutnings_id"]}')

        update_item_data(data, item=item)

        set_state(state)