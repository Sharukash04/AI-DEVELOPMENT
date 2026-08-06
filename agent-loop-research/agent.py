import os
import json
import re
import time
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any

load_dotenv()

class ResearchAgent:
    def __init__(self):
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("Please set GROQ_API_KEY in .env file")
        
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"
        
        self.iteration_log = []
        self.max_iterations = 5
        self.current_iteration = 0
        
        self.tools = {
            'web_search': self.web_search,
            'fetch_page': self.fetch_page
        }

    def web_search(self, query: str) -> Dict[str, Any]:
        """Search using multiple fallback methods"""
        print(f"   🔍 Searching for: {query}")
        
        # Method 1: Try DuckDuckGo Lite (less blocking)
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            response = requests.get(
                'https://lite.duckduckgo.com/lite/',
                params={'q': query},
                headers=headers,
                timeout=15
            )
            print(f"   📡 Status: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                results = []
                
                # DuckDuckGo Lite results
                for link in soup.find_all('a', class_='result-link'):
                    text = link.get_text(strip=True)
                    if text and len(text) > 20:
                        results.append(text)
                
                # Also try result snippets
                for snippet in soup.find_all('td', class_='result-snippet'):
                    text = snippet.get_text(strip=True)
                    if text and len(text) > 20:
                        results.append(text)
                
                if results:
                    print(f"   ✅ Found {len(results)} results!")
                    return {'success': True, 'results': results[:3], 'query': query}
                else:
                    print(f"   ⚠️ No results parsed from page")
                    
        except Exception as e:
            print(f"   ❌ Method 1 failed: {e}")
        
        # Method 2: Try regular DuckDuckGo HTML
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(
                'https://html.duckduckgo.com/html/',
                params={'q': query},
                headers=headers,
                timeout=15
            )
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                results = []
                for result in soup.find_all('a', class_='result__a'):
                    parent = result.find_parent('div', class_='result__body')
                    if parent:
                        snippet = parent.find('a', class_='result__snippet')
                        if snippet:
                            text = snippet.get_text(strip=True)
                            if len(text) > 10:
                                results.append(text)
                if results:
                    print(f"   ✅ Found {len(results)} results (Method 2)!")
                    return {'success': True, 'results': results[:3], 'query': query}
        except Exception as e:
            print(f"   ❌ Method 2 failed: {e}")
        
        # Method 3: Try Wikipedia API as fallback
        try:
            print(f"   🔄 Trying Wikipedia fallback...")
            wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}"
            response = requests.get(wiki_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                extract = data.get('extract', '')
                if extract:
                    print(f"   ✅ Wikipedia found info!")
                    return {'success': True, 'results': [extract[:500]], 'query': query}
        except Exception as e:
            print(f"   ❌ Wikipedia failed: {e}")
        
        print(f"   ❌ All search methods failed")
        return {'success': False, 'error': 'No results found from any source', 'query': query}

    def fetch_page(self, url: str) -> Dict[str, Any]:
        """Fetch and extract text from a webpage"""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                for script in soup(["script", "style"]):
                    script.decompose()
                text = soup.get_text()
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)
                return {'success': True, 'content': text[:1000], 'url': url}
        except Exception as e:
            return {'success': False, 'error': str(e), 'url': url}
        return {'success': False, 'error': 'Failed to fetch page'}

    def call_llm(self, prompt: str) -> str:
        """Call Groq LLM with retry on rate limit"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"   🤖 Calling LLM (attempt {attempt + 1})...")
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a helpful AI research agent. Respond ONLY with valid JSON when asked for a plan."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                result = response.choices[0].message.content
                print(f"   ✅ LLM responded!")
                return result
            except Exception as e:
                print(f"   ⚠️ LLM attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    print(f"   ❌ LLM failed after {max_retries} attempts")
                    return ""
        return ""

    def perceive(self, query: str) -> Dict[str, Any]:
        """Stage 1: Perceive - understand the query"""
        print(f"\n🤔 Perceiving: {query}")
        return {
            'query': query,
            'iteration': self.current_iteration,
            'knowledge': [],
            'needs_more_info': True
        }

    def plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Stage 2: Plan - ask LLM what to do next"""
        print(f"\n🧠 Planning iteration {self.current_iteration + 1}")
        prompt = f"""You are an AI research agent. Current query: "{state['query']}"
You have these tools: web_search, fetch_page
You know so far: {state.get('knowledge', [])}

Plan your next action:
1. Which tool to use? (web_search or fetch_page)
2. What parameters?
3. Why this action?

Respond in **valid JSON** with keys: action, parameters, reasoning.
Example: {{"action": "web_search", "parameters": {{"query": "climate change solutions"}}, "reasoning": "Need more sources"}}"""
        
        try:
            raw_output = self.call_llm(prompt)
            print(f"   📝 Raw LLM output: {raw_output[:200]}...")
            
            json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
            if json_match:
                plan = json.loads(json_match.group())
                print(f"   ✅ Parsed plan: {plan}")
            else:
                print(f"   ⚠️ No JSON found, using default")
                plan = {
                    'action': 'web_search',
                    'parameters': {'query': state['query']},
                    'reasoning': 'Default (no JSON found)'
                }
        except Exception as e:
            print(f"   ⚠️ Plan error: {e}")
            plan = {
                'action': 'web_search',
                'parameters': {'query': state['query']},
                'reasoning': f'Fallback due to error: {str(e)}'
            }
        state['plan'] = plan
        return state

    def act(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Stage 3: Act - execute the planned action"""
        print(f"\n⚡ Executing: {state['plan'].get('action')}")
        plan = state['plan']
        action = plan.get('action')
        params = plan.get('parameters', {})
        
        if action in self.tools:
            try:
                result = self.tools[action](**params)
                if result.get('success', False):
                    state['last_action_result'] = result
                    print(f"   ✅ Action successful: {action}")
                else:
                    print(f"   ⚠️ Tool failed: {result.get('error', 'Unknown error')}")
                    state['last_action_result'] = result
                    state['error_handled'] = True
            except Exception as e:
                print(f"   ❌ Tool exception: {e}")
                state['last_action_result'] = {'success': False, 'error': str(e)}
                state['error_handled'] = True
        else:
            state['last_action_result'] = {'success': False, 'error': f'Unknown action: {action}'}
            state['error_handled'] = True
        return state

    def observe(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Stage 4: Observe - process results"""
        print(f"\n👀 Observing results")
        result = state.get('last_action_result', {})
        
        if result.get('success'):
            if state['plan'].get('action') == 'web_search' and result.get('results'):
                state['knowledge'].extend(result['results'])
                print(f"   📚 Added {len(result['results'])} facts to knowledge")
            elif state['plan'].get('action') == 'fetch_page' and result.get('content'):
                state['knowledge'].append(result['content'][:200])
                print(f"   📄 Added page content to knowledge")
        else:
            print(f"   🔄 Tool failed, will retry with different approach next iteration")
            
        state['success_condition_met'] = self.check_success(state)
        self.log_iteration(state)
        return state

    def check_success(self, state: Dict[str, Any]) -> bool:
        """Check if we have enough information"""
        if len(state.get('knowledge', [])) >= 3:
            print(f"   🎯 Success: Have {len(state['knowledge'])} facts!")
            return True
        if state.get('last_action_result', {}).get('success', False) and 'content' in state['last_action_result']:
            return True
        return False

    def log_iteration(self, state: Dict[str, Any]):
        """Log every iteration to JSON file"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'iteration': self.current_iteration,
            'perceive': {'query': state.get('query')},
            'plan': state.get('plan'),
            'act': state.get('last_action_result'),
            'observe': {
                'knowledge_count': len(state.get('knowledge', [])),
                'success_condition_met': state.get('success_condition_met', False)
            }
        }
        self.iteration_log.append(log_entry)
        with open('iteration_log.json', 'w') as f:
            json.dump(self.iteration_log, f, indent=2)
        print(f"   📝 Logged iteration {self.current_iteration}")

    def write_final_answer(self, query: str, knowledge: list) -> str:
        """Write final answer using gathered knowledge"""
        print(f"\n📝 Writing final answer...")
        if not knowledge:
            return "Sorry, I couldn't find any information about that topic."
        
        all_notes = "\n\n".join(knowledge)
        
        prompt = f"""You are a helpful research assistant.

The user asked: "{query}"

Here are the facts you found from web research:
{all_notes}

Please write a clear, final answer to the user's question.
Use the facts above. Keep it short (3-5 sentences).
If you are not sure about something, say so."""
        
        try:
            answer = self.call_llm(prompt)
            print(f"   ✅ Final answer written!")
            return answer
        except Exception as e:
            print(f"   ❌ Could not write answer: {e}")
            return "Sorry, I could not write the final answer."

    def run(self, query: str) -> Dict[str, Any]:
        """Main agent loop"""
        print(f"\n🚀 Starting Research Agent")
        print(f"📌 Query: {query}")
        print(f"🔄 Max iterations: {self.max_iterations}\n")
        
        state = {'query': query}
        
        while self.current_iteration < self.max_iterations:
            print(f"\n{'='*60}")
            print(f"ITERATION {self.current_iteration + 1}")
            print(f"{'='*60}")
            
            state = self.perceive(query)
            state = self.plan(state)
            state = self.act(state)
            state = self.observe(state)
            
            self.current_iteration += 1
            
            if state.get('success_condition_met', False):
                print(f"\n🎯 Success condition met! Stopping.")
                break
        
        # Final answer
        print(f"\n{'='*60}")
        print(f"✅ RESEARCH COMPLETE")
        print(f"{'='*60}")
        print(f"Total iterations: {self.current_iteration}")
        print(f"Knowledge gathered: {len(state.get('knowledge', []))}")
        print(f"Log saved to: iteration_log.json")
        
        final_answer = self.write_final_answer(query, state.get('knowledge', []))
        print(f"\n{'='*60}")
        print(f"📋 FINAL ANSWER:")
        print(f"{'='*60}")
        print(final_answer)
        
        state['final_answer'] = final_answer
        with open('final_answer.txt', 'w') as f:
            f.write(final_answer)
        print(f"\n💾 Final answer saved to: final_answer.txt")
        
        return state

def main():
    print("🤖 AI Research Agent (Powered by Groq)")
    print("=" * 50)
    try:
        agent = ResearchAgent()
    except ValueError as e:
        print(f"Error: {e}")
        return
    
    print("\nExample queries:")
    print("1. Who is APJ Abdul Kalam?")
    print("2. What are the benefits of renewable energy?")
    print("3. What is machine learning?")
    
    query = input("\nEnter your research query: ").strip()
    if not query:
        query = "Who is APJ Abdul Kalam?"
    
    agent.run(query)

if __name__ == "__main__":
    main()