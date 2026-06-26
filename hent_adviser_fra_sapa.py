from q_sapa.functionality.launch import launch_sapa
from q_sapa.functionality.advis_soeg import soeg_advis


async def hent_adviser(page, session) -> list:
    print("🔍 Henter adviser fra SAPA...")

    try:
        # ✅ Login / navigation
        await launch_sapa(page=page, session=session, advis=True)

        # ✅ Kør søgning
        resultater = await soeg_advis(
            page=page,
            session=session,
            tekst="Arbejdsskadehændelser",
        )

        return resultater

    finally:
        # ✅ VIGTIGT:
        # Session må IKKE lukkes her – det styres i main.py
        pass
