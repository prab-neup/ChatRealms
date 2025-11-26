from dotenv import load_dotenv
import os 
import json
import re
from openai import AsyncOpenAI
import aiohttp
import asyncio

load_dotenv()

class AIClient:
    def __init__(self,base_url = "http://localhost:3002"):
        self.client = AsyncOpenAI(
            api_key = os.getenv('OPENAI_API_KEY'),
            base_url = os.getenv('BASE_URL'),
            default_query= {"api-version": "2024-04-01-preview"},
        )
        self.base_url = base_url
        self.session = None
        
        
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                'Content-Type': 'application/json',
                
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        
        
    async def get_ai_response(self,conversation:str,prompt:str,followup_prompt:str):
        print("First prompt",prompt )
        print("Sec prompt",followup_prompt )
    
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Conversation: {conversation}"}
                    ],
                temperature=0.2,
                

            )
        except Exception as e:
            print(f"Error in OpenAI API call: {e}")
            return None

        translated_json = response.choices[0].message.content
        print( "\nRaw ai response : " ,translated_json)
        
        try:
            data_json = json.loads(translated_json)
        except json.JSONDecodeError:
            # fallback: extract JSON using regex if AI added extra text
            match = re.search(r"\{.*\}", translated_json, re.DOTALL)
            if match:
                data_json = json.loads(match.group())
            else:
                raise ValueError("No valid JSON found in AI response")
        
        if data_json["search"] == "no" and data_json["query"] == "no":
            print("AI decided no need to respond.")
            return None
        
        elif data_json.get("search") == "no" and data_json.get("query"):
            return data_json.get("query")
            
        elif data_json.get("search") == "yes" and data_json.get("query"):
            try:
                search_and_scrape = await  self.ScrapeSite(data_json.get("query"))
                if search_and_scrape:
                    try:
                        resp = await self.client.chat.completions.create(
                            model="gpt-4.1",
                            messages=[
                                
                                {"role": "system", "content": followup_prompt},
                                {"role": "user", "content": f"Conversation: {conversation}"},
                                {"role": "assistant", "content": f"Here is the information I found from the web: {search_and_scrape}"}
                            ],
                            temperature=0.2
                        )
                    except Exception as e:
                        print(f"Error in AI API call: {e}")
                        return None  
                                                       
                    final_response = resp.choices[0].message.content
                    
                    try:
                        data_json = json.loads(final_response)
                    except json.JSONDecodeError:
                    # fallback: extract JSON using regex if AI added extra text
                        match = re.search(r"\{.*\}", final_response, re.DOTALL)
                        if match:
                            data_json = json.loads(match.group())
                        else:
                            raise ValueError("No valid JSON found in AI response")
                    
                    
                    
                    
                    cleaned_text = self.clean_ai_response(data_json.get("text"))    
                    return cleaned_text
                else:
                    return None
            except Exception as e:
                print(f"Error during web search ")
                return None             

        else:
            return None
        
    async def search_for_sites(self, query, limit=3):
        """Simple search using Firecrawl"""
        endpoints = "/v1/search"  # Using v1 which is more stable"
        payload = {
            "query": query,
            "limit": limit
        }
        
        try:
            url = f"{self.base_url}{endpoints}"
            print(f"Searching with endpoint: {endpoints}")
            print(f"Query: {query}")
            
            async with self.session.post(url, json=payload, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success'):
                        print(f"Search successful, found {len(data.get('data', []))} results")
                        return data
                    else:
                        print(f"API error: {data.get('error')}")
                        return None
                else:
                    print(f"HTTP {response.status}")
                    print(f"Response: {await response.text()}")
                    
                    
        except Exception as e:
            print(f"Endpoint failed: {e}")
        
        return None
    
    
    
    


    def clean_ai_response(self,text: str) -> str:
        """
        Cleans AI-generated text by removing escape characters, extra whitespace,
        and Markdown formatting symbols like '*' and '**'.
        """
        if not text:
            return ""

        # Decode escaped newlines/tabs
        cleaned = text.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "")

        # Remove non-printable control characters
        cleaned = re.sub(r'[\x00-\x1F\x7F]', '', cleaned)

        # Remove Markdown-style emphasis symbols
        # Removes *word*, **word**, or lone asterisks used in lists
        cleaned = re.sub(r'\*{1,2}([^*]+?)\*{1,2}', r'\1', cleaned)
        cleaned = re.sub(r'^\s*\*\s+', '', cleaned, flags=re.MULTILINE)  # bullet points

        # Collapse multiple newlines
        cleaned = re.sub(r'\n\s*\n+', '\n\n', cleaned)

        # Collapse multiple spaces
        cleaned = re.sub(r' {2,}', ' ', cleaned)

        # Trim leading/trailing whitespace
        cleaned = cleaned.strip()

        return cleaned

    
    
    async def ScrapeSite(self,query:str) -> str:
        """Simple scraping using Firecrawl"""
        data = await self.search_for_sites(query, limit=3)
        if not data or not data.get('data'):
            print("No search results found")
            return None


        for site in data["data"]:
            url = site.get('url')
            
            endpoints = "/v1/scrape"  # Using v1 which is more stable"
            payload = {

                "url": url,
                "formats": ["markdown"],
                "onlyMainContent": True
                
            }
            try:
                full_url = f"{self.base_url}{endpoints}"
                print(f"Scraping with endpoint: {endpoints}")
                print(f"URL: {url}")
                
                async with self.session.post(full_url, json=payload, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success'):
                            print(f"Scraping successful for {url}")
                            return data
                        else:
                            print(f"API error: {data.get('error')}")
                            continue
                    else:
                        print(f"HTTP {response.status}")
                        print(f"Response is: {await response.text()}")
                        continue
                        
            except Exception as e:
                print(f"Endpoint failed: {e}")
                continue
        
        
        return None
        
    
            
# if __name__ == "__main__":
#     import asyncio

#     async def main():
#         context = """
#         Shrek:I am not felling very well these days.
#         Donkey:Oh no! What's wrong?
#         Shrek:I have been feeling very anxious and stressed out lately.
#         Donkey:Have you tried talking to someone about it?
#         Shrek:Not yet, I don't know where to start.
#         Donkey:Maybe you could start by seeing a therapist or counselor.
#         Shrek:I don't why i feel this way, I have a good life.
#         AI Response: Hey Shrek, it's actually pretty common to feel anxious or stressed even when things seem to be going well on the outside. Sometimes our minds and bodies react to things we aren't even fully aware of. Talking to a therapist or counselor can really help you figure out what's going on and give you some tools to manage those feelings. You're definitely not alone in this, and reaching out is a strong first step. If you want, I can share some tips on how to start that conversation or ways to cope in the meantime.
#         Shrek: Can you tell me some coping mechanisms i can use right now base on popular web sites?
#         """


#         prompt1 = "You are an Psychology expert who is part of a social medai group. You want to help them if they feel like they want some help in mental wellbeing. Given the conversation, decide if you need to partcipate in the conversation. If you, as a psychologist, think the conversation requires your support you have two option do. First, you decided that this conversation don't need psychologist therefore you respond with json {\"search\":\"no\",\"query\":\"no\". In second scenario you think you need to help them. If you decided to respond, you again have two choices. First one is respond without the help of web. It might be because the conversatinal need is simple enough for you to advice on your own without you needing to collect enough information from web.The second case is the topic is serious and they need facts and information that is beyond your knowledge so that you would be supposed more reliable and professional, so you need to search web to find concrete answer. In this first case, where you don't need web search,  you need to simply return your response strictly in json format like this {\"search \":\"no\",\"query\":\"Your respose to the chat without web search\"}. But you decide to be more accurate and precise in respond than send response  in JSON format in this way {\"search\":\"yes\",\"query\":\"Short query that instruct search engine to fetch the information you need to return\"}'. "
#         prompt2 = "You are an Psychology expert who is part of a social medai group. You want to help them if they feel like they want some advice.  Analyze the converation and find the answers form the web content provided to you form the assistent. Make sure you vibe with the conversation going on and answer is brief covering important details. The respose should strictly be in JSON format {\"text\":\"Your detailed answer based on the conversation and web search results\"}."
#         async with AIClient() as ai_client:
#             response = await ai_client.get_ai_response(context, prompt1,prompt2)
#             print("Search Response:", response)
            
#         # response = await ai_client.get_ai_response(context, prompt1,prompt2)
#         # print("AI Response:", response)


#     asyncio.run(main())
