def behandel_page(item):

    from q_haderslev_vbo.automation_server.ats_update_item_data import update_item_data
    from q_haderslev_vbo.automation_server.ats_find_state import find_state
    import logging
    logger = logging.getLogger(__name__)

    data = item.data

    # ==========================================================
    # 🧠 STATES
    # ==========================================================
    class States:
        SEND_BREV = "1.0 Brev sendt"
        JOURNALISER_BREV = "1.5 Brev journaliseret"
        AFSLUT_SAG = "2.0 Sag afsluttet"


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
    step = "SEND_BREV"
    # ==========================================================
    state = getattr(States, step)

    if mangler_state(state):

        log_step(step, "Start")

        data["box"]["brev_sendt_id"] = 123
        log_step(step, f'ID sat: {data["box"]["brev_sendt_id"]}')

        update_item_data(data, item=item)

        set_state(state)


    # ==========================================================
    step = "JOURNALISER_BREV"
    # ==========================================================
    state = getattr(States, step)

    if mangler_state(state):

        log_step(step, "Start")

        data["box"]["journal_id"] = 456
        log_step(step, f'ID sat: {data["box"]["journal_id"]}')

        update_item_data(data, item=item)

        set_state(state)


    # ==========================================================
    step = "AFSLUT_SAG"
    # ==========================================================
    state = getattr(States, step)

    if mangler_state(state):

        log_step(step, "Start")

        data["box"]["afslutnings_id"] = 789
        log_step(step, f'ID sat: {data["box"]["afslutnings_id"]}')

        update_item_data(data, item=item)

        set_state(state)