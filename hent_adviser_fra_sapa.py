from q_sapa.soeg import soeg_advis


# ==================================================
# ✅ HENT ADVISER (KALDES FRA MAIN)
# ==================================================
async def hent_adviser(
    page,
    debug: bool = False
) -> list:

    print("🔍 Henter adviser fra SAPA...")

    # ---------------------------------------------
    # ✅ Kør samlet søgeflow
    # ---------------------------------------------
    resultater = await soeg(
        page=page,
        tekst="Arbejdsskadehændelser",
        debug=debug
    )

    return resultater