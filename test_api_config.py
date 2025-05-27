"""Test script to verify API configurations."""

import asyncio
import logging
from config import load_config
from services.katalon_service import KatalonStudioAssistService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_api_calls():
    """Test both LL1 and LL2 API configurations."""
    config = load_config("generate_code")
    service = KatalonStudioAssistService(config)
    
    test_prompt = "// Generate a test to verify login functionality"
    
    # Test LL1
    logger.info("\n" + "="*60)
    logger.info("Testing LL1 Configuration")
    logger.info("="*60)
    
    ll1_result = service.call_api(
        feature="generate_code",
        prompt=test_prompt,
        config={"mode": "script"},
        prompt_id="generate-code",
        llm="LL1"
    )
    
    if "error" not in ll1_result:
        logger.info(f"LL1 Success! Config: {ll1_result.get('llm_config')}")
        logger.info(f"Output preview: {ll1_result['api_output'][:200]}...")
    else:
        logger.error(f"LL1 Failed: {ll1_result['error']}")
    
    # Test LL2
    logger.info("\n" + "="*60)
    logger.info("Testing LL2 Configuration")
    logger.info("="*60)
    
    ll2_result = service.call_api(
        feature="generate_code",
        prompt=test_prompt,
        config={"mode": "script"},
        prompt_id="generate-code",
        llm="LL2"
    )
    
    if "error" not in ll2_result:
        logger.info(f"LL2 Success! Config: {ll2_result.get('llm_config')}")
        logger.info(f"Output preview: {ll2_result['api_output'][:200]}...")
    else:
        logger.error(f"LL2 Failed: {ll2_result['error']}")
    
    # Compare
    if "error" not in ll1_result and "error" not in ll2_result:
        logger.info("\n" + "="*60)
        logger.info("COMPARISON")
        logger.info("="*60)
        logger.info(f"LL1 output length: {len(ll1_result['api_output'])}")
        logger.info(f"LL2 output length: {len(ll2_result['api_output'])}")
        logger.info(f"LL1 uses: {ll1_result['llm_config']['type']}")
        logger.info(f"LL2 uses: {ll2_result['llm_config']['type']}")


if __name__ == "__main__":
    asyncio.run(test_api_calls())