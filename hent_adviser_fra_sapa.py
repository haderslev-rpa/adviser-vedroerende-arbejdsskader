from q_sapa.launch import launch_sapa
from q_sapa.advis_soeg import soeg_advis

async def hent_adviser(page, session) -> list:
    print("🔍 Henter adviser fra SAPA...")

    try:

        # ✅ Login / navigation
        await session.recorder.start_recording(120)
        await launch_sapa(page=page, session=session, advis=True,)

        # ✅ Kør søgning
        resultater = await soeg_advis(
            page=page,
            session=session,
            tekst="Arbejdsskadehændelser",
        )

        return resultater

    finally:
        # ✅ Luk kun hvis vi selv startede
        if session:
            print("🛑 Lukker browser")
            await session.close()