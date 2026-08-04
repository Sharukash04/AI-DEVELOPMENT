import os
import json
import re
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any

load_dotenv()

class ResearchAgent:
    def __init__(self):
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("Please set GOOGLE_API_KEY in .env file")
        
        genai.configure(api_key=api_key)
        # 🆕 FIXED: Updated model name!
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        self.iteration_log = []
        self.max_iterations = 5
        self.current_iteration = 0
        
        self.tools = {
            'web_search': self.web_search,
            'fetch_page': self.fetch_page
        }

    # 🆕 FIXED: Better web search with fallback
    def web_search(self, query: str) -> Dict[str, Any]:
        try:
            # Try DuckDuckGo HTML version first (more reliable)
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
                            results.append(snippet.get_text(strip=True))
                if results:
                    return {'success': True, 'results': results[:3], 'query': query}
            
            # Fallback: Try JSON API
            response = requests.get(
                'https://api.duckduckgo.com/',
                params={'q': query, 'format': 'json'},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get('RelatedTopics', [])[:3]:
                    if 'Text' in item:
                        results.append(item['Text'])
                if results:
                    return {'success': True, 'results': results, 'query': query}
                    
        except Exception as e:
            return {'success': False, 'error': str(e), 'query': query}
        return {'success': False, 'error': 'No results found'}

    def fetch_page(self, url: str) -> Dict[str, Any]:
        try:
            response = requests.get(url, timeout=10)
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

    def perceive(self, query: str) -> Dict[str, Any]:
        print(f"\n🤔 Perceiving: {query}")
        return {
            'query': query,
            'iteration': self.current_iteration,
            'knowledge': [],
            'needs_more_info': True
        }

    def plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        print(f"\n🧠 Planning iteration {self.current_iteration + 1}")
        prompt = f"""
        You are an AI research agent. Current query: "{state['query']}"
        You have these tools: web_search, fetch_page
        You know so far: {state.get('knowledge', [])}
        
        Plan your next action:
        1. Which tool to use? (web_search or fetch_page)
        2. What parameters?
        3. Why this action?
        
        Respond in **valid JSON** with keys: action, parameters, reasoning.
        Example: {{"action": "web_search", "parameters": {{"query": "climate change solutions"}}, "reasoning": "Need more sources"}}
        """
        try:
            response = self.model.generate_content(prompt)
            raw_output = response.text
            json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
            if json_match:
                plan = json.loads(json_match.group())
            else:
                plan = {
                    'action': 'web_search',
                    'parameters': {'query': state['query']},
                    'reasoning': 'Default (no JSON)'
                }
        except Exception as e:
            print(f"⚠️ Gemini error: {e}")
            plan = {
                'action': 'web_search',
                'parameters': {'query': state['query']},
                'reasoning': f'Fallback: {str(e)}'
            }
        state['plan'] = plan
        return state

    def act(self, state: Dict[str, Any]) -> Dict[str, Any]:
        print(f"\n⚡ Executing: {state['plan'].get('action')}")
        plan = state['plan']
        action = plan.get('action')
        params = plan.get('parameters', {})
        if action in self.tools:
            try:
                result = self.tools[action](**params)
                if result.get('success', False):
                    state['last_action_result'] = result
                    print(f"✅ Action successful: {action}")
                else:
                    print(f"⚠️ Tool failed: {result.get('error', 'Unknown error')}")
                    state['last_action_result'] = result
                    state['error_handled'] = True
            except Exception as e:
                print(f"❌ Tool exception: {e}")
                state['last_action_result'] = {'success': False, 'error': str(e)}
                state['error_handled'] = True
        else:
            state['last_action_result'] = {'success': False, 'error': f'Unknown action: {action}'}
            state['error_handled'] = True
        return state

    def observe(self, state: Dict[str, Any]) -> Dict[str, Any]:
        print(f"\n👀 Observing results")
        result = state.get('last_action_result', {})
        if result.get('success'):
            if state['plan'].get('action') == 'web_search' and result.get('results'):
                state['knowledge'].extend(result['results'])
            elif state['plan'].get('action') == 'fetch_page' and result.get('content'):
                state['knowledge'].append(result['content'][:200])
        state['success_condition_met'] = self.check_success(state)
        self.log_iteration(state)
        return state

    def check_success(self, state: Dict[str, Any]) -> bool:
        if len(state.get('knowledge', [])) >= 3:
            return True
        if state.get('last_action_result', {}).get('success', False) and 'content' in state['last_action_result']:
            return True
        return False

    def log_iteration(self, state: Dict[str, Any]):
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
        print(f"📝 Logged iteration {self.current_iteration}")

    def write_final_answer(self, query: str, knowledge: list) -> str:
        print(f"\n📝 Writing final answer...")
        if not knowledge:
            return "Sorry, I couldn't find any information about that topic."
        
        all_notes = "\n\n".join(knowledge)
        
        prompt = f"""
        You are a helpful research assistant.
        
        The user asked: "{query}"
        
        Here are the facts you found from web research:
        {all_notes}
        
        Please write a clear, final answer to the user's question.
        Use the facts above. Keep it short (3-5 sentences).
        If you are not sure about something, say so.
        """
        
        try:
            response = self.model.generate_content(prompt)
            answer = response.text
            print(f"✅ Final answer written!")
            return answer
        except Exception as e:
            print(f"❌ Could not write answer: {e}")
            return "Sorry, I could not write the final answer."

    def run(self, query: str) -> Dict[str, Any]:
        print(f"\n🚀 Starting Research Agent")
        print(f"📌 Query: {query}")
        print(f"🔄 Max iterations: {self.max_iterations}\n")
        state = {'query': query}
        while self.current_iteration < self.max_iterations:
            print(f"\n{'='*50}")
            print(f"ITERATION {self.current_iteration + 1}")
            print(f"{'='*50}")
            state = self.perceive(query)
            state = self.plan(state)
            state = self.act(state)
            state = self.observe(state)
            self.current_iteration += 1
            if state.get('success_condition_met', False):
                print(f"\n🎯 Success condition met! Stopping.")
                break
        
        print(f"\n{'='*50}")
        print(f"✅ RESEARCH COMPLETE")
        print(f"{'='*50}")
        print(f"Total iterations: {self.current_iteration}")
        print(f"Knowledge gathered: {len(state.get('knowledge', []))}")
        print(f"Log saved to: iteration_log.json")
        
        final_answer = self.write_final_answer(query, state.get('knowledge', []))
        print(f"\n{'='*50}")
        print(f"📋 FINAL ANSWER:")
        print(f"{'='*50}")
        print(final_answer)
        
        state['final_answer'] = final_answer
        with open('final_answer.txt', 'w') as f:
            f.write(final_answer)
        print(f"\n💾 Final answer saved to: final_answer.txt")
        
        return state

def main():
    print("🤖 AI Research Agent")
    print("=" * 40)
    try:
        agent = ResearchAgent()
    except ValueError as e:
        print(f"Error: {e}")
        return
    print("\nExample queries:")
    print("1. Latest developments in AI")
    print("2. Climate change solutions")
    print("3. Space exploration news")
    query = input("\nEnter your research query: ").strip()
    if not query:
        query = "Latest developments in artificial intelligence"
    agent.run(query)

if __name__ == "__main__":
    main()