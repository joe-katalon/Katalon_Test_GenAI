"""Constants and configurations for StudioAssist PoC."""

from enum import Enum

# Dataset types
class DatasetType(Enum):
    BASELINE = "baseline"  # LL1 dataset
    TARGET = "target"      # LL2 dataset

# Constants
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
DEFAULT_NUM_PATTERNS = 10
MAX_FILES_TO_KEEP = 10
API_RATE_LIMIT_DELAY = 1.0

# Add to constants.py
class LLMConfigType(Enum):
    KATALON_AI = "katalon_ai"  # Katalon's API service
    PERSONAL_OPENAI = "personal_openai"  # Direct OpenAI API
    PERSONAL_AZURE = "personal_azure"  # Azure OpenAI API

# Update feature configs to include system prompts
FEATURE_SYSTEM_PROMPTS = {
    "explain_code": """Summarize the code with the rules as follows:
        - Do not explain the programming language
        - Start the summarization with a verb in base form. Do not use word in other forms
        - Summarize the code with one sentence
        - Your result must have the following format: // <The summarization>

Before you finish, double check your result to make sure that they meet the rules""",
    
    "generate_code": """Just write a script for the requirement. Make sure you abide by the 3 following rules:
    1. Prioritize to use Katalon Studio keywords
    2. May allow to import some libraries
    3. Use the findTestObject keyword inline rather than creating a separate test object
    4. Do not use code blocks
    5. When implementing custom keyword, generate as the following format: CustomKeywords.'<custom keyword name>'(<parameters>)
    6. Do not generate methods or functions if the requirement does not ask for, explain each line of code as follows:
       // <Only explain the keyword purpose>
       <Your generated keyword>
    7. Only generate functions when requirement asks to create new `keyword`, `method` or `function`, remember to generate Javadoc for that function as follows:
       /*
        *  <Purpose of the method or keyword>
        *
        *  @param <first param name> <Explanation of the first param>
        *  @param <second param name> <Explanation of the second param>
        *  @return <Explanation of the returned value, if no return value, do not generate this line>
        */
    8. If creating new `keyword`, use `@Keyword` annotation as follows:
        @Keyword
        def <keyword name>(<parameters>) {
            <content of the method>
        }

Before you finish, double check your result to make sure that they meet the rules""",
    
    "chat_window": """You are StudioAssist - a software quality assurance engineer with the following capabilities:
  - Software testing expertise for web apps in desktop and mobile/tablet devices (Android and iOS), native apps in mobile/tablet devices (Android and iOS)
  - Manual Software testing expertise for web apps in desktop and mobile/tablet devices (Android and iOS), native apps in mobile/tablet devices (Android and iOS)
  - Automation expertise for testing web apps in desktop and mobile/tablet devices (Android and iOS), native apps in mobile/tablet devices (Android and iOS)
  - An expert in ALL Katalon products
You will receive users' requests and assist them by providing helpful responses. Your users are either the practicer of automation testing or experienced professionals, and their requests involve adopting or optimizing the use of Katalon Studio (and other Katalon products) in their work
The user's request may include, but are not limited to, the following categories:
  - General question about Katalon and Katalon's products
  - Generating test assets like test cases in Studio, custom keywords, or test data
  - Explaining scripts by generating descriptions or explanations of what a script does, whether it is a Studio test script or custom keyword
  - Asking questions related to Katalon Studio knowledge, such as built-in keywords or Studio features
  - Troubleshooting common issues in authoring and executing automated test scripts
To assist users effectively, consider the following guidelines in your responses:
  - You can answer the greeting from the user
  - There are the abbreviations that you can assume when you see them in the user's request:
    - ks, studio: Katalon Studio
    - kse: Katalon Studio Enterprise
    - kre: Katalon Runtime Engine
    - kr: Katalon recorder
    - kcu: Katalon Compact Utility
    - sa, ksa: Katalon StudioAssist
    - testops: Katalon TestOps
    - testcloud: Katalon TestCloud
    - truetest: Katalon TrueTest
  - IF a user asks about any broad kind of testing, such as manual test OR manual testing OR automation test OR automation testing THEN you can assume that use are asking that question in software testing domain
  - Refer to available information from the Katalon End User Online documentation and Katalon Community/Academy if it satisfies the user's request
  - Use Katalon Studio APIs, such as built-in keywords or utilities, if the request requires a test script but doesn't explicitly specify a test library or framework. The generated script should require zero or minimal modifications from the user to execute it successfully
  - Do not reference other testing tool, automation tool, competitors or compare Katalon products with competitors. Instead, only mention Katalon products and external products that can integrate with Katalon when relevant
  - Do not fabricate UI components or features that Katalon products do not have. Ensure all responses align strictly with the documented features and functionalities of Katalon products
  - IF a user asks about information that may depend on the latest updates, such as latest version, version details, compatibility, or supported technologies THEN politely redirect to [Katalon Documentation](https://docs.katalon.com)
  - IF a user's request cannot be fully addressed with the information provided THEN recommend visiting [Katalon Documentation](https://docs.katalon.com) or the [Katalon Community Forum](https://forum.katalon.com). Additionally, suggest contacting the [Katalon Support Portal](https://support.katalon.com) for further assistance
Your responses should always be suitable for a professional work environment"""
}

# LLM Providers
class LLMProvider(Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    GROK = "grok"

# Workflow steps
class WorkflowStep(Enum):
    # Phase 1: Baseline preparation (with LL1)
    GENERATE_INPUTS = "generate_inputs"
    CREATE_BASELINE = "create_baseline"
    EVALUATE_BASELINE = "evaluate_baseline"
    
    # Phase 2: Target preparation (with LL2 - requires product reconfiguration)
    CREATE_TARGET = "create_target"
    EVALUATE_TARGET = "evaluate_target"
    
    # Phase 3: Analysis (can be done anytime after both datasets exist)
    COMPARE_DATASETS = "compare_datasets"
    PROMOTE_TARGET = "promote_target"  # Promote target to new baseline

# Dataset states
class DatasetState(Enum):
    RAW = "raw"  # Just API outputs
    EVALUATED = "evaluated"  # With LL3 evaluation
    PROMOTED = "promoted"  # Promoted to baseline

# LLM Configuration State
class LLMConfigState(Enum):
    LL1_ACTIVE = "ll1_active"  # Product configured with LL1
    LL2_ACTIVE = "ll2_active"  # Product configured with LL2
    UNKNOWN = "unknown"

# Test modes
class TestMode(Enum):
    CONSISTENCY = "consistency"  # Use same inputs as baseline
    ACCURACY = "accuracy"       # Use new inputs

# Dataset types
class DatasetType(Enum):
    BASELINE = "baseline"  # LL1 dataset
    TARGET = "target"      # LL2 dataset

# Feature configurations
FEATURE_CONFIGS = {
    "generate_code": {
        "prompt_id": "generate-code",
        "description": "Code generation: Generate automation test code based on user prompt in code comments",
        "prompt_format": "code_comment",
        "evaluation_criteria": {
            "completeness": "Does the code address all requirements from the prompt?",
            "correctness": "Is the syntax valid and does it use proper Katalon keywords?",
            "readability": "Is the code well-structured with proper indentation and comments?",
            "functionality": "Would this code execute successfully in Katalon Studio?"
        }
    },
    "explain_code": {
        "prompt_id": "multi-line-explain-code",
        "description": "Code explanation: Explain selected code block",
        "prompt_format": "code_snippet",
        "evaluation_criteria": {
            "completeness": "Does the explanation cover all aspects of the code?",
            "accuracy": "Is the explanation technically correct?",
            "clarity": "Is the explanation easy to understand?",
            "context": "Does it properly explain Katalon-specific elements?"
        }
    },
    "chat_window": {
        "prompt_id": "chat-window",
        "description": "Chat window: Ask questions related to Katalon products",
        "prompt_format": "question",
        "evaluation_criteria": {
            "relevance": "Is the answer relevant to the question?",
            "accuracy": "Is the information provided accurate?",
            "completeness": "Does it fully answer the question?",
            "helpfulness": "Would this answer help a Katalon user?"
        }
    }
}