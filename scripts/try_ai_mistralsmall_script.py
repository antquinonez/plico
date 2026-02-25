# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.
#
# WARNING: This code contains sensitive technology requiring explicit authorization
# for possession or use. Unauthorized possession is strictly prohibited and will
# result in legal action. Licensed use requires signed agreement and compliance
# with all security requirements.
#
# Contact: antquinonez@farfiner.com

import logging
import os

import matplotlib.pyplot as plt

from src.Clients.FFMistralSmall import FFMistralSmall as LLM
from src.FFAI import FFAI as AI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# ===============================================================================

# Create the client
api_key = os.getenv("MISTRALSMALL_KEY")
azure_client = LLM(
    model="mistral-small-2503",
    api_key=api_key,
)
logger.info("Azure client created")

# Create the wrapper
ffai = AI(
    azure_client,
    persist_dir="./ffai_data",
    persist_name="mistral_session",
    auto_persist=True,  # Change to True for immediate persistence
)
logger.info("AI wrapper created with persistence support")


# Generate responses and track history
logger.info("Generating responses...")

response = ffai.generate_response("How do I use AI?")
logger.info(f"Response to 'How do I use AI?': {response}")

response = ffai.generate_response("how are you?", prompt_name="greeting")
logger.info(f"Response to greeting: {response}")

response = ffai.generate_response("what is 2 +2?", prompt_name="math")
logger.info(f"Response to math question: {response}")

response = ffai.generate_response("concatenate these words: cat, dog ", prompt_name="pet")
logger.info(f"Response to concatenation: {response}")

ffai.clear_conversation()
logger.info("Conversation cleared")

logger.info(
    "============================================================================================================================================================================="
)
response = ffai.generate_response(
    "what did you say to the math problem?",
    prompt_name="final query",
    history=["pet", "math", "greeting"],
)
logger.info("RESPONSE:")
logger.info(response)
logger.info("============================")

logger.info(
    "============================================================================================================================================================================="
)
response = ffai.generate_response("concatenate these words again: cat, dog,shrimp ")
logger.info(f"Response to second concatenation: {response}")

logger.info(
    "============================================================================================================================================================================="
)
ffai.clear_conversation()
logger.info("Conversation cleared")
logger.info(
    "============================================================================================================================================================================="
)

# The history will now include both the 'final query' and its associated history
logger.info(
    "======================================================================================"
)
response = ffai.generate_response(
    "what did you say to the question?",
    prompt_name="really final query",
    history=["final query"],
)

logger.info(f"Final response: {response}")

logger.info(
    "======================================================================================"
)
response = ffai.generate_response(
    "Was that a hard question? Why not?",
    prompt_name="really final query",
    history=["final query"],
)

logger.info(f"Final response: {response}")

logger.info(
    "======================================================================================"
)
response = ffai.generate_response(
    "What is the level of difficulty of the question asked?",
    prompt_name="really final query",
    history=["final query"],
)


logger.info(
    "======================================================================================"
)
response = ffai.generate_response(
    "What is the level of difficulty of the question asked?",
    prompt_name="really final query",
    history=["final query"],
)


logger.info(
    "======================================================================================"
)
response = ffai.generate_response(
    "What is the level of difficulty of the question asked?",
    prompt_name="really final query",
    history=["final query"],
)

logger.info(
    "======================================================================================"
)
response = ffai.generate_response(
    "What is the level of difficulty of the question asked?",
    prompt_name="really final query",
    history=["final query"],
)


logger.info(f"Final response: {response}")

logger.info(
    "============================================================================================================================================================================="
)
response = ffai.generate_response(
    "what did you say to the question? Also, how do i spell cat? Respond with a JSON dict.",
    prompt_name="really final query",
    history=["final query"],
)
logger.info(f"Final response: {response}")


# Access history using any of the interface methods
history = ffai.get_interaction_history()
clean_history = ffai.get_clean_interaction_history()
attr_history = ffai.get_prompt_attr_history()


latest = ffai.get_latest_interaction()
stats = ffai.get_model_usage_stats()
prompt_dict = ffai.get_prompt_dict()
formatted_responses = ffai.get_formatted_responses(["math"])

logger.info(
    "============================================================================================================================================================================="
)
logger.info("Interaction History:")
logger.info(history)
logger.info(
    "============================================================================================================================================================================="
)
logger.info("Clean Interaction History:")
logger.info(clean_history)
logger.info(
    "============================================================================================================================================================================="
)
logger.info("Prompt Attr History:")
logger.info(attr_history)
logger.info(
    "============================================================================================================================================================================="
)
logger.info("Latest Interaction:")
logger.info(latest)
logger.info(
    "============================================================================================================================================================================="
)
logger.info("Model Usage Stats:")
logger.info(stats)
logger.info(
    "============================================================================================================================================================================="
)
logger.info("Prompt Dictionary:")
logger.info(prompt_dict)
logger.info(
    "============================================================================================================================================================================="
)
logger.info("Formatted Responses:")
logger.info(formatted_responses)

# ------------------------------
# NEW DATAFRAME DEMONSTRATIONS
# ------------------------------
logger.info(
    "============================================================================================================================================================================="
)
logger.info("DATAFRAME DEMONSTRATIONS")
logger.info(
    "============================================================================================================================================================================="
)

# 1. Basic DataFrame Conversions
logger.info("1. Converting history to DataFrame")
history_df = ffai.history_to_dataframe()
logger.info(f"History DataFrame shape: {history_df.shape}")
logger.info("History DataFrame columns:")
logger.info(history_df.columns)
logger.info("History DataFrame:")
logger.info(history_df.head())
logger.info(
    "============================================================================================================================================================================="
)

logger.info("2. Converting clean history to DataFrame")
clean_history_df = ffai.clean_history_to_dataframe()
logger.info(f"Clean History DataFrame shape: {clean_history_df.shape}")
logger.info("Clean History DataFrame:")
logger.info(clean_history_df.head())
logger.info(
    "============================================================================================================================================================================="
)

logger.info("3. Converting prompt attribute history to DataFrame")
prompt_attr_df = ffai.prompt_attr_history_to_dataframe()
logger.info(f"Prompt Attribute DataFrame shape: {prompt_attr_df.shape}")
logger.info("Prompt Attribute DataFrame:")
logger.info(prompt_attr_df.head())
logger.info(
    "============================================================================================================================================================================="
)

logger.info("4. Converting ordered history to DataFrame")
ordered_df = ffai.ordered_history_to_dataframe()
logger.info(f"Ordered History DataFrame shape: {ordered_df.shape}")
logger.info("Ordered History DataFrame:")
logger.info(ordered_df.head())
logger.info(
    "============================================================================================================================================================================="
)

# 2. Search and Analysis
logger.info("5. Searching history for 'concatenate'")
concatenate_results = ffai.search_history(text="concatenate")
logger.info(f"Search results shape: {concatenate_results.shape}")
logger.info("Search results:")
logger.info(concatenate_results)
logger.info(
    "============================================================================================================================================================================="
)

logger.info("6. Searching history by prompt name")
math_results = ffai.search_history(prompt_name="math")
logger.info(f"Math prompt results shape: {math_results.shape}")
logger.info("Math prompt results:")
logger.info(math_results)
logger.info(
    "============================================================================================================================================================================="
)

# 3. Statistics
logger.info("7. Model usage statistics")
model_stats_df = ffai.get_model_stats_df()
logger.info("Model usage statistics:")
logger.info(model_stats_df)
logger.info(
    "============================================================================================================================================================================="
)

logger.info("8. Prompt name usage statistics")
prompt_name_stats_df = ffai.get_prompt_name_stats_df()
logger.info("Prompt name usage statistics:")
logger.info(prompt_name_stats_df)
logger.info(
    "============================================================================================================================================================================="
)

logger.info("9. Interaction counts by date")
date_counts = ffai.interaction_counts_by_date()
logger.info("Interaction counts by date:")
logger.info(date_counts)
logger.info(
    "============================================================================================================================================================================="
)

# 4. Advanced Analysis
if not history_df.is_empty():
    logger.info("10. Advanced analysis: Response length by prompt name")

    # FIX: Use a UDF (user-defined function) to calculate string length instead of the lengths() method
    try:
        # Convert to pandas for more straightforward string length calculation
        pd_df = history_df.to_pandas()
        pd_df["response_length"] = pd_df["response"].str.len()

        # Group by prompt_name and calculate average response length
        response_lengths = pd_df.groupby("prompt_name")["response_length"].mean().reset_index()
        response_lengths = response_lengths.sort_values("response_length", ascending=False)

        logger.info("Average response length by prompt name:")
        logger.info(response_lengths)

    except Exception as e:
        logger.error(f"Error in response length analysis: {str(e)}")

    logger.info(
        "============================================================================================================================================================================="
    )

    # Optional: Visualization if matplotlib is available
    try:
        # Find the most used prompt names and their response lengths
        pd_df = history_df.to_pandas()
        pd_df["response_length"] = pd_df["response"].str.len()

        # Filter out null prompt names and calculate average response length
        response_by_prompt = (
            pd_df[pd_df["prompt_name"].notnull()]
            .groupby("prompt_name")["response_length"]
            .mean()
            .reset_index()
        )
        response_by_prompt = response_by_prompt.sort_values("response_length", ascending=False)

        if len(response_by_prompt) > 0:
            # Create simple bar chart
            plt.figure(figsize=(10, 6))
            plt.bar(response_by_prompt["prompt_name"], response_by_prompt["response_length"])
            plt.title("Average Response Length by Prompt Name")
            plt.xlabel("Prompt Name")
            plt.ylabel("Average Response Length (chars)")
            plt.xticks(rotation=45, ha="right")
            plt.tight_layout()

            # Save plot
            plt.savefig("response_length_by_prompt.png")
            logger.info("Plot saved to 'response_length_by_prompt.png'")
    except Exception as e:
        logger.error(f"Error creating visualization: {str(e)}")

logger.info("Script execution completed")
