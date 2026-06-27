import aiohttp
import config
import database
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Prices per 1,000,000 tokens
PRICING = {
    "GEMINI": {
        "input": 0.075,
        "output": 0.30
    },
    "DEEPSEEK": {
        "input": 0.14,
        "output": 0.28
    }
}

async def generate_response(prompt: str, system_instruction: str = "") -> str:
    """
    Calls the active AI provider configured in database.settings.
    Integrates cost calculation and logs usage into MongoDB.
    """
    provider = database.settings.get("ai_provider", "GEMINI").upper()
    if provider not in ["GEMINI", "DEEPSEEK"]:
        provider = "GEMINI"
        
    ai_enabled = database.settings.get("ai_enabled", True)
    if not ai_enabled:
        return "⚠️ AI funksiyalari o'chirilgan."

    # Construct the final prompt using system instruction context if present
    full_prompt = prompt
    if system_instruction:
        full_prompt = f"{system_instruction}\n\nFoydalanuvchi so'rovi:\n{prompt}"

    if provider == "GEMINI":
        api_key = config.GEMINI_API_KEY
        if not api_key:
            logger.error("GEMINI_API_KEY is not configured in environment variables.")
            return "⚠️ Gemini API kaliti topilmadi. Iltimos, admin bilan bog'laning."
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [{"text": full_prompt}]
            }]
        }
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Gemini API returned status {response.status}: {error_text}")
                        return "⚠️ Gemini serveridan noto'g'ri javob oldik. Iltimos, qayta urinib ko'ring."
                        
                    res_json = await response.json()
                    candidates = res_json.get("candidates", [])
                    if not candidates:
                        return "⚠️ Gemini hech qanday javob qaytarmadi."
                        
                    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    
                    usage = res_json.get("usageMetadata", {})
                    input_tokens = usage.get("promptTokenCount", 0)
                    output_tokens = usage.get("candidatesTokenCount", 0)
                    
                    await log_usage("GEMINI", input_tokens, output_tokens)
                    return text
        except Exception as e:
            logger.error(f"Error querying Gemini API: {e}", exc_info=True)
            return "⚠️ Gemini API bilan bog'lanishda xatolik yuz berdi (Vaqt tugadi yoki tarmoq xatosi)."

    elif provider == "DEEPSEEK":
        api_key = config.DEEPSEEK_API_KEY
        if not api_key:
            logger.error("DEEPSEEK_API_KEY is not configured in environment variables.")
            return "⚠️ DeepSeek API kaliti topilmadi. Iltimos, admin bilan bog'laning."
            
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": full_prompt}
            ],
            "stream": False
        }
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"DeepSeek API returned status {response.status}: {error_text}")
                        return "⚠️ DeepSeek serveridan noto'g'ri javob oldik. Iltimos, qayta urinib ko'ring."
                        
                    res_json = await response.json()
                    choices = res_json.get("choices", [])
                    if not choices:
                        return "⚠️ DeepSeek hech qanday javob qaytarmadi."
                        
                    text = choices[0].get("message", {}).get("content", "")
                    
                    usage = res_json.get("usage", {})
                    input_tokens = usage.get("prompt_tokens", 0)
                    output_tokens = usage.get("completion_tokens", 0)
                    
                    await log_usage("DEEPSEEK", input_tokens, output_tokens)
                    return text
        except Exception as e:
            logger.error(f"Error querying DeepSeek API: {e}", exc_info=True)
            return "⚠️ DeepSeek API bilan bog'lanishda xatolik yuz berdi (Vaqt tugadi yoki tarmoq xatosi)."

async def log_usage(provider: str, input_tokens: int, output_tokens: int):
    """
    Computes estimated dollar cost and accumulates it in settings.
    Saves a log entry into MongoDB 'ai_logs' collection.
    """
    rates = PRICING.get(provider, {"input": 0, "output": 0})
    input_cost = (input_tokens / 1_000_000) * rates["input"]
    output_cost = (output_tokens / 1_000_000) * rates["output"]
    total_cost = input_cost + output_cost
    
    # Accumulate in settings
    ai_analytics = database.settings.setdefault("ai_analytics", {
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost": 0.0
    })
    
    ai_analytics["total_input_tokens"] = ai_analytics.get("total_input_tokens", 0) + input_tokens
    ai_analytics["total_output_tokens"] = ai_analytics.get("total_output_tokens", 0) + output_tokens
    ai_analytics["total_cost"] = ai_analytics.get("total_cost", 0.0) + total_cost
    
    # Persist setting updates instantly to settings collection
    if database.settings_col is not None:
        try:
            await database.settings_col.update_one(
                {"_id": "global"},
                {"$set": {"ai_analytics": ai_analytics}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to update global settings in MongoDB: {e}")
            
    # Insert detailed audit log
    if database.db is not None:
        try:
            ai_logs_col = database.db["ai_logs"]
            log_doc = {
                "timestamp": datetime.now().isoformat(),
                "provider": provider,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": total_cost
            }
            await ai_logs_col.insert_one(log_doc)
        except Exception as e:
            logger.error(f"Failed to insert audit log in MongoDB: {e}")
