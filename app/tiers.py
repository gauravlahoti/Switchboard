# LLM tier IDs — placeholders until verified with gcloud
# Run: gcloud ai model-garden models list --project=adk-deploy-trail | grep -i gemini
# Check the CAN_PREDICT column is Yes. IDs often carry a -preview suffix.
TIER_SMALL    = "gemini-3.8-flash"  # TODO: verify CAN_PREDICT
TIER_MID      = "gemini-3.8-flash"  # TODO: replace with actual mid-tier ID
TIER_FRONTIER = "gemini-3.8-flash"  # TODO: replace with actual frontier ID


def model_for_complexity(complexity: float) -> str:
    """Map Jev's complexity Noul (0-1) to a Gemini model tier.

    0.3/0.7 thresholds per TypeSafe guidance; middle band gets its own row.
    """
    if complexity < 0.3:
        return TIER_SMALL
    if complexity <= 0.7:
        return TIER_MID
    return TIER_FRONTIER
