#!/usr/bin/env python3
"""
HTML Structure Analyzer - Ferramenta para análise de estrutura HTML
Facilita a criação de crawlers identificando elementos importantes
Execute:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from urllib.parse import urlparse, urljoin
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any
import time
import platform

# Configuração específica para Windows
if platform.system() == 'Windows':
    import asyncio
    import asyncio.windows_events
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Configurações da página
st.set_page_config(
    page_title="HTML Structure Analyzer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Importações condicionais com fallback
USE_SELECTOLAX = False
try:
    from selectolax.parser import HTMLParser
    test_doc = HTMLParser("<div>test</div>")
    if hasattr(test_doc, 'css') and hasattr(test_doc, 'css_first'):
        USE_SELECTOLAX = True
    else:
        from lxml import html as lxml_html
        import lxml
except ImportError:
    pass

if not USE_SELECTOLAX:
    try:
        from lxml import html as lxml_html
        import lxml
    except ImportError:
        st.error("❌ Nenhum parser HTML disponível. Instale selectolax ou lxml:")
        st.code("pip install selectolax")
        st.code("# OU")
        st.code("pip install lxml")
        st.stop()

# Driver para renderização
DRIVER_TYPE = None
try:
    from playwright.sync_api import sync_playwright
    DRIVER_TYPE = "playwright"
except ImportError:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        DRIVER_TYPE = "selenium"
    except ImportError:
        pass

import requests
from urllib.robotparser import RobotFileParser

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def get_domain(url: str) -> str:
    """Extrai o domínio de uma URL"""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def parse_html(html_content: str):
    """Parse HTML usando selectolax ou lxml"""
    if USE_SELECTOLAX:
        return HTMLParser(html_content)
    else:
        return lxml_html.fromstring(html_content)

def get_xpath(element) -> str:
    """Gera XPath completo para um elemento"""
    if USE_SELECTOLAX:
        # Para selectolax, gera um XPath aproximado
        return "//element"  # Simplificado
    else:
        # Para lxml, usa o método getpath
        if hasattr(element, 'getroottree'):
            tree = element.getroottree()
            return tree.getpath(element)
        else:
            # Fallback: constrói XPath manualmente
            path_parts = []
            current = element
            while current is not None and hasattr(current, 'tag'):
                tag = current.tag
                parent = current.getparent()
                if parent is not None:
                    siblings = [e for e in parent if hasattr(e, 'tag') and e.tag == tag]
                    if len(siblings) > 1:
                        index = siblings.index(current) + 1
                        path_parts.append(f"{tag}[{index}]")
                    else:
                        path_parts.append(tag)
                else:
                    path_parts.append(tag)
                current = parent
            return '/' + '/'.join(reversed(path_parts))

# =============================================================================
# CARREGAMENTO DE PÁGINA
# =============================================================================

def load_page_requests(url: str, user_agent: str = None) -> Tuple[str, str]:
    """Carrega página usando requests (sem JavaScript)"""
    headers = {'User-Agent': user_agent} if user_agent else {}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text, response.url

def load_page_playwright(url: str, user_agent: str = None) -> Tuple[str, str]:
    """Carrega página com Playwright"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            context = browser.new_context(
                user_agent=user_agent if user_agent else 'Mozilla/5.0',
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1000)
            content = page.content()
            final_url = page.url
            browser.close()
            return content, final_url
    except Exception as e:
        raise Exception(f"Erro no Playwright: {str(e)}")

def load_page_selenium(url: str, user_agent: str = None) -> Tuple[str, str]:
    """Carrega página com Selenium"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    if user_agent:
        options.add_argument(f'user-agent={user_agent}')
    
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        time.sleep(2)
        content = driver.page_source
        final_url = driver.current_url
        return content, final_url
    finally:
        driver.quit()

def load_page(url: str, user_agent: str = None) -> Tuple[str, str]:
    """Carrega página usando o melhor método disponível"""
    if DRIVER_TYPE == "playwright":
        try:
            return load_page_playwright(url, user_agent)
        except:
            return load_page_requests(url, user_agent)
    elif DRIVER_TYPE == "selenium":
        try:
            return load_page_selenium(url, user_agent)
        except:
            return load_page_requests(url, user_agent)
    else:
        return load_page_requests(url, user_agent)

# =============================================================================
# ANÁLISE DE LISTAS
# =============================================================================

def analyze_lists(html_content: str) -> Dict:
    """Analisa todas as listas (ul/ol) na página"""
    doc = parse_html(html_content)
    results = {
        'navigation_menus': [],
        'content_lists': [],
        'galleries': [],
        'other_lists': []
    }
    
    if USE_SELECTOLAX:
        # Encontra todas as UL e OL
        lists = doc.css('ul, ol')
        
        for lst in lists:
            list_type = lst.tag
            
            # Pega o container pai
            parent = lst.parent if hasattr(lst, 'parent') else None
            parent_tag = parent.tag if parent and hasattr(parent, 'tag') else 'body'
            parent_attrs = parent.attrs if parent and hasattr(parent, 'attrs') else {}
            
            # Pega os items
            items = lst.css('li')
            
            # Analisa características
            total_items = len(items)
            items_with_links = 0
            items_with_images = 0
            total_text_length = 0
            
            list_items_data = []
            for item in items:  # Pega TODOS os items, não apenas 10
                item_text = item.text(strip=True) if hasattr(item, 'text') else ''
                has_link = bool(item.css_first('a'))
                has_image = bool(item.css_first('img'))
                
                items_with_links += 1 if has_link else 0
                items_with_images += 1 if has_image else 0
                total_text_length += len(item_text)
                
                # Pega o HTML do item
                try:
                    item_html = item.html if hasattr(item, 'html') else ''
                except:
                    item_html = ''
                
                list_items_data.append({
                    'text': item_text,
                    'has_link': has_link,
                    'has_image': has_image,
                    'html': item_html[:500]  # Limita para não ficar muito grande
                })
            
            avg_text_length = total_text_length / max(len(list_items_data), 1)
            
            # Gera seletor CSS
            list_attrs = lst.attrs if hasattr(lst, 'attrs') else {}
            if list_attrs.get('id'):
                css_selector = f"#{list_attrs['id']}"
            elif list_attrs.get('class'):
                css_selector = f".{list_attrs['class'].split()[0]}"
            else:
                css_selector = list_type
            
            # Pega o HTML da lista
            try:
                html_sample = lst.html if hasattr(lst, 'html') else ''
                # Se o HTML for muito grande, pega apenas o início
                if len(html_sample) > 1000:
                    html_sample = html_sample[:1000] + '...'
            except:
                html_sample = ''
            
            list_info = {
                'type': list_type,
                'total_items': total_items,
                'css_selector': css_selector,
                'xpath': f"//{list_type}",
                'parent_tag': parent_tag,
                'parent_class': parent_attrs.get('class', ''),
                'items_preview': list_items_data[:10],  # Preview limitado para visualização
                'all_items': list_items_data,  # TODOS os items
                'avg_text_length': avg_text_length,
                'items_with_links': items_with_links,
                'items_with_images': items_with_images,
                'html_sample': html_sample
            }
            
            # Classificação inteligente
            if items_with_links == len(list_items_data) and avg_text_length < 50:
                results['navigation_menus'].append(list_info)
            elif avg_text_length > 100:
                results['content_lists'].append(list_info)
            elif items_with_images > len(list_items_data) / 2:
                results['galleries'].append(list_info)
            else:
                results['other_lists'].append(list_info)
    
    else:  # lxml
        lists = doc.xpath('//ul | //ol')
        
        for lst in lists:
            list_type = lst.tag
            parent = lst.getparent()
            parent_tag = parent.tag if parent is not None else 'body'
            parent_class = parent.get('class', '') if parent is not None else ''
            
            items = lst.xpath('.//li')
            total_items = len(items)
            items_with_links = 0
            items_with_images = 0
            total_text_length = 0
            
            list_items_data = []
            for item in items:  # Pega TODOS os items
                item_text = item.text_content().strip() if hasattr(item, 'text_content') else ''
                has_link = bool(item.xpath('.//a'))
                has_image = bool(item.xpath('.//img'))
                
                items_with_links += 1 if has_link else 0
                items_with_images += 1 if has_image else 0
                total_text_length += len(item_text)
                
                # Pega o HTML do item
                try:
                    from lxml import html as lxml_html
                    item_html = lxml_html.tostring(item, encoding='unicode', method='html')[:500]
                except:
                    item_html = ''
                
                list_items_data.append({
                    'text': item_text,
                    'has_link': has_link,
                    'has_image': has_image,
                    'html': item_html
                })
            
            avg_text_length = total_text_length / max(len(list_items_data), 1)
            
            # Gera seletor CSS
            list_id = lst.get('id', '')
            list_class = lst.get('class', '')
            if list_id:
                css_selector = f"#{list_id}"
            elif list_class:
                css_selector = f".{list_class.split()[0]}"
            else:
                css_selector = list_type
            
            # XPath completo
            xpath = get_xpath(lst)
            
            # HTML sample
            try:
                from lxml import html as lxml_html
                html_sample = lxml_html.tostring(lst, encoding='unicode', method='html')
                if len(html_sample) > 1000:
                    html_sample = html_sample[:1000] + '...'
            except:
                html_sample = ''
            
            list_info = {
                'type': list_type,
                'total_items': total_items,
                'css_selector': css_selector,
                'xpath': xpath,
                'parent_tag': parent_tag,
                'parent_class': parent_class,
                'items_preview': list_items_data[:10],
                'all_items': list_items_data,  # TODOS os items
                'avg_text_length': avg_text_length,
                'items_with_links': items_with_links,
                'items_with_images': items_with_images,
                'html_sample': html_sample
            }
            
            # Classificação
            if items_with_links == len(list_items_data) and avg_text_length < 50:
                results['navigation_menus'].append(list_info)
            elif avg_text_length > 100:
                results['content_lists'].append(list_info)
            elif items_with_images > len(list_items_data) / 2:
                results['galleries'].append(list_info)
            else:
                results['other_lists'].append(list_info)
    
    return results

# =============================================================================
# ANÁLISE DE FORMULÁRIOS
# =============================================================================

def analyze_forms(html_content: str) -> Dict:
    """Analisa todos os formulários e inputs na página"""
    doc = parse_html(html_content)
    results = {
        'forms': [],
        'standalone_inputs': []
    }
    
    if USE_SELECTOLAX:
        # Analisa forms
        forms = doc.css('form')
        for form in forms:
            form_attrs = form.attrs if hasattr(form, 'attrs') else {}
            
            # Coleta inputs dentro do form
            inputs = form.css('input, textarea, select, button')
            input_types = defaultdict(int)
            
            for inp in inputs:
                inp_type = inp.attrs.get('type', 'text') if hasattr(inp, 'attrs') else 'text'
                input_types[inp_type] += 1
            
            # Seletor CSS
            if form_attrs.get('id'):
                css_selector = f"form#{form_attrs['id']}"
            elif form_attrs.get('class'):
                css_selector = f"form.{form_attrs['class'].split()[0]}"
            else:
                css_selector = 'form'
            
            # Pega o HTML do form
            try:
                html_sample = form.html if hasattr(form, 'html') else ''
                if len(html_sample) > 500:
                    html_sample = html_sample[:500] + '...'
            except:
                html_sample = ''
            
            results['forms'].append({
                'action': form_attrs.get('action', ''),
                'method': form_attrs.get('method', 'GET'),
                'name': form_attrs.get('name', ''),
                'id': form_attrs.get('id', ''),
                'class': form_attrs.get('class', ''),
                'css_selector': css_selector,
                'xpath': '//form',
                'input_count': len(inputs),
                'input_types': dict(input_types),
                'html_sample': html_sample
            })
        
        # Inputs fora de forms
        all_inputs = doc.css('input, textarea, select')
        form_inputs = []
        for form in forms:
            form_inputs.extend(form.css('input, textarea, select'))
        
        for inp in all_inputs:
            if inp not in form_inputs:
                inp_attrs = inp.attrs if hasattr(inp, 'attrs') else {}
                
                # HTML do input
                try:
                    html_sample = inp.html if hasattr(inp, 'html') else ''
                    if len(html_sample) > 200:
                        html_sample = html_sample[:200]
                except:
                    html_sample = ''
                
                results['standalone_inputs'].append({
                    'tag': inp.tag,
                    'type': inp_attrs.get('type', 'text'),
                    'name': inp_attrs.get('name', ''),
                    'id': inp_attrs.get('id', ''),
                    'placeholder': inp_attrs.get('placeholder', ''),
                    'css_selector': f"{inp.tag}#{inp_attrs['id']}" if inp_attrs.get('id') else inp.tag,
                    'xpath': f"//{inp.tag}",
                    'html_sample': html_sample
                })
    
    else:  # lxml
        forms = doc.xpath('//form')
        for form in forms:
            inputs = form.xpath('.//input | .//textarea | .//select | .//button')
            input_types = defaultdict(int)
            
            for inp in inputs:
                inp_type = inp.get('type', 'text')
                input_types[inp_type] += 1
            
            form_id = form.get('id', '')
            form_class = form.get('class', '')
            
            if form_id:
                css_selector = f"form#{form_id}"
            elif form_class:
                css_selector = f"form.{form_class.split()[0]}"
            else:
                css_selector = 'form'
            
            try:
                from lxml import html as lxml_html
                html_sample = lxml_html.tostring(form, encoding='unicode', method='html')
                if len(html_sample) > 500:
                    html_sample = html_sample[:500] + '...'
            except:
                html_sample = ''
            
            results['forms'].append({
                'action': form.get('action', ''),
                'method': form.get('method', 'GET'),
                'name': form.get('name', ''),
                'id': form_id,
                'class': form_class,
                'css_selector': css_selector,
                'xpath': get_xpath(form),
                'input_count': len(inputs),
                'input_types': dict(input_types),
                'html_sample': html_sample
            })
        
        # Inputs fora de forms
        all_inputs = doc.xpath('//input | //textarea | //select')
        for inp in all_inputs:
            parent = inp.getparent()
            while parent is not None:
                if parent.tag == 'form':
                    break
                parent = parent.getparent()
            
            if parent is None or parent.tag != 'form':
                inp_id = inp.get('id', '')
                css_selector = f"{inp.tag}#{inp_id}" if inp_id else inp.tag
                
                try:
                    from lxml import html as lxml_html
                    html_sample = lxml_html.tostring(inp, encoding='unicode', method='html')
                    if len(html_sample) > 200:
                        html_sample = html_sample[:200]
                except:
                    html_sample = ''
                
                results['standalone_inputs'].append({
                    'tag': inp.tag,
                    'type': inp.get('type', 'text'),
                    'name': inp.get('name', ''),
                    'id': inp_id,
                    'placeholder': inp.get('placeholder', ''),
                    'css_selector': css_selector,
                    'xpath': get_xpath(inp),
                    'html_sample': html_sample
                })
    
    return results

# =============================================================================
# ANÁLISE DE LINKS
# =============================================================================

def analyze_navigation(html_content: str, base_url: str) -> Dict:
    """Analisa links de navegação"""
    doc = parse_html(html_content)
    results = {
        'internal_links': [],
        'external_links': [],
        'navigation_patterns': {}
    }
    
    domain = get_domain(base_url)
    
    if USE_SELECTOLAX:
        links = doc.css('a[href]')
        
        for link in links[:100]:  # Limita para performance
            link_attrs = link.attrs if hasattr(link, 'attrs') else {}
            href = link_attrs.get('href', '')
            text = link.text(strip=True) if hasattr(link, 'text') else ''
            
            # Classifica link
            if href.startswith('http'):
                if domain in href:
                    link_type = 'internal'
                else:
                    link_type = 'external'
            elif href.startswith('/'):
                link_type = 'internal'
                href = urljoin(base_url, href)
            elif href.startswith('#'):
                link_type = 'anchor'
            else:
                link_type = 'relative'
                href = urljoin(base_url, href)
            
            # Parent info
            parent = link.parent if hasattr(link, 'parent') else None
            parent_tag = parent.tag if parent and hasattr(parent, 'tag') else ''
            
            # HTML do link
            try:
                html_sample = link.html if hasattr(link, 'html') else ''
                if len(html_sample) > 200:
                    html_sample = html_sample[:200]
            except:
                html_sample = ''
            
            link_info = {
                'text': text[:50],
                'href': href,
                'type': link_type,
                'parent_tag': parent_tag,
                'css_selector': f"a[href='{href[:50]}']",
                'html_sample': html_sample
            }
            
            if link_type == 'internal':
                results['internal_links'].append(link_info)
            elif link_type == 'external':
                results['external_links'].append(link_info)
    
    else:  # lxml
        links = doc.xpath('//a[@href]')
        
        for link in links[:100]:
            href = link.get('href', '')
            text = link.text_content().strip() if hasattr(link, 'text_content') else ''
            
            # Classifica link
            if href.startswith('http'):
                if domain in href:
                    link_type = 'internal'
                else:
                    link_type = 'external'
            elif href.startswith('/'):
                link_type = 'internal'
                href = urljoin(base_url, href)
            elif href.startswith('#'):
                link_type = 'anchor'
            else:
                link_type = 'relative'
                href = urljoin(base_url, href)
            
            parent = link.getparent()
            parent_tag = parent.tag if parent is not None else ''
            
            try:
                from lxml import html as lxml_html
                html_sample = lxml_html.tostring(link, encoding='unicode', method='html')
                if len(html_sample) > 200:
                    html_sample = html_sample[:200]
            except:
                html_sample = ''
            
            link_info = {
                'text': text[:50],
                'href': href,
                'type': link_type,
                'parent_tag': parent_tag,
                'css_selector': f"a[href='{href[:50]}']",
                'xpath': get_xpath(link),
                'html_sample': html_sample
            }
            
            if link_type == 'internal':
                results['internal_links'].append(link_info)
            elif link_type == 'external':
                results['external_links'].append(link_info)
    
    # Detecta padrões de navegação
    nav_containers = defaultdict(list)
    for link in results['internal_links'][:50]:
        if link['parent_tag']:
            nav_containers[link['parent_tag']].append(link)
    
    # Identifica containers com múltiplos links (prováveis menus)
    for tag, links in nav_containers.items():
        if len(links) >= 3:
            results['navigation_patterns'][tag] = {
                'link_count': len(links),
                'sample_links': links[:5]
            }
    
    return results

# =============================================================================
# ANÁLISE DE TÍTULOS E CONTEÚDO
# =============================================================================

def analyze_content_structure(html_content: str) -> Dict:
    """Analisa estrutura de conteúdo (títulos, parágrafos, etc)"""
    doc = parse_html(html_content)
    results = {
        'headings': defaultdict(list),
        'content_blocks': [],
        'tables': []
    }
    
    if USE_SELECTOLAX:
        # Títulos
        for level in range(1, 7):
            headings = doc.css(f'h{level}')
            for h in headings[:20]:
                text = h.text(strip=True) if hasattr(h, 'text') else ''
                if text:
                    # HTML do heading
                    try:
                        html_sample = h.html if hasattr(h, 'html') else ''
                        if len(html_sample) > 200:
                            html_sample = html_sample[:200]
                    except:
                        html_sample = ''
                    
                    results['headings'][f'h{level}'].append({
                        'text': text[:100],
                        'css_selector': f'h{level}',
                        'html_sample': html_sample
                    })
        
        # Blocos de conteúdo (div com texto substancial)
        divs = doc.css('div, article, section')
        for div in divs[:50]:
            text = div.text(strip=True) if hasattr(div, 'text') else ''
            if len(text) > 200:  # Div com conteúdo substancial
                div_attrs = div.attrs if hasattr(div, 'attrs') else {}
                results['content_blocks'].append({
                    'tag': div.tag,
                    'class': div_attrs.get('class', ''),
                    'id': div_attrs.get('id', ''),
                    'text_length': len(text),
                    'text_preview': text[:200],
                    'css_selector': f"#{div_attrs['id']}" if div_attrs.get('id') else div.tag
                })
        
        # Tabelas
        tables = doc.css('table')
        for table in tables[:10]:
            rows = table.css('tr')
            cols = table.css('th, td')
            table_attrs = table.attrs if hasattr(table, 'attrs') else {}
            
            # HTML da tabela
            try:
                html_sample = table.html if hasattr(table, 'html') else ''
                if len(html_sample) > 300:
                    html_sample = html_sample[:300] + '...'
            except:
                html_sample = ''
            
            results['tables'].append({
                'rows': len(rows),
                'cells': len(cols),
                'class': table_attrs.get('class', ''),
                'id': table_attrs.get('id', ''),
                'css_selector': f"#{table_attrs['id']}" if table_attrs.get('id') else 'table',
                'html_sample': html_sample
            })
    
    else:  # lxml
        # Títulos
        for level in range(1, 7):
            headings = doc.xpath(f'//h{level}')
            for h in headings[:20]:
                text = h.text_content().strip() if hasattr(h, 'text_content') else ''
                if text:
                    try:
                        from lxml import html as lxml_html
                        html_sample = lxml_html.tostring(h, encoding='unicode', method='html')
                        if len(html_sample) > 200:
                            html_sample = html_sample[:200]
                    except:
                        html_sample = ''
                    
                    results['headings'][f'h{level}'].append({
                        'text': text[:100],
                        'css_selector': f'h{level}',
                        'xpath': get_xpath(h),
                        'html_sample': html_sample
                    })
        
        # Blocos de conteúdo
        divs = doc.xpath('//div | //article | //section')
        for div in divs[:50]:
            text = div.text_content().strip() if hasattr(div, 'text_content') else ''
            if len(text) > 200:
                div_id = div.get('id', '')
                div_class = div.get('class', '')
                
                results['content_blocks'].append({
                    'tag': div.tag,
                    'class': div_class,
                    'id': div_id,
                    'text_length': len(text),
                    'text_preview': text[:200],
                    'css_selector': f"#{div_id}" if div_id else div.tag,
                    'xpath': get_xpath(div)
                })
        
        # Tabelas
        tables = doc.xpath('//table')
        for table in tables[:10]:
            rows = table.xpath('.//tr')
            cols = table.xpath('.//th | .//td')
            
            table_id = table.get('id', '')
            table_class = table.get('class', '')
            
            try:
                from lxml import html as lxml_html
                html_sample = lxml_html.tostring(table, encoding='unicode', method='html')
                if len(html_sample) > 300:
                    html_sample = html_sample[:300] + '...'
            except:
                html_sample = ''
            
            results['tables'].append({
                'rows': len(rows),
                'cells': len(cols),
                'class': table_class,
                'id': table_id,
                'css_selector': f"#{table_id}" if table_id else 'table',
                'xpath': get_xpath(table),
                'html_sample': html_sample
            })
    
    return results

# =============================================================================
# INTERFACE PRINCIPAL
# =============================================================================

def main():
    st.title("🔍 HTML Structure Analyzer")
    st.markdown("**Ferramenta para análise de estrutura HTML** - Facilita a criação de web crawlers identificando elementos importantes")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # URL
        st.markdown("### 🌐 URL para analisar")
        
        # URLs de exemplo
        example_urls = {
            "": "",
            "Hacker News": "https://news.ycombinator.com/",
            "Wikipedia": "https://en.wikipedia.org/wiki/Web_scraping",
            "GitHub": "https://github.com/trending"
        }
        
        selected_example = st.selectbox(
            "Exemplos rápidos:",
            options=list(example_urls.keys()),
            index=0
        )
        
        url = st.text_input(
            "Digite a URL:",
            value=example_urls.get(selected_example, ''),
            placeholder="https://example.com"
        )
        
        # User Agent
        user_agent = st.text_input(
            "User-Agent (opcional)",
            value="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        # Método de carregamento
        st.markdown("### 🚀 Método de carregamento")
        
        if DRIVER_TYPE == "playwright":
            st.success("✅ Playwright disponível")
            render_js = st.checkbox("Renderizar JavaScript", value=True)
        elif DRIVER_TYPE == "selenium":
            st.warning("⚠️ Selenium disponível")
            render_js = st.checkbox("Renderizar JavaScript", value=True)
        else:
            st.info("ℹ️ Apenas requests disponível")
            render_js = False
            st.caption("Para renderizar JavaScript, instale Playwright ou Selenium")
        
        # Parser
        st.markdown("### 📝 Parser HTML")
        if USE_SELECTOLAX:
            st.success("✅ Usando Selectolax (rápido)")
        else:
            st.info("ℹ️ Usando lxml (completo)")
        
        # Botão de análise
        analyze_button = st.button(
            "🔍 Analisar Estrutura",
            type="primary",
            use_container_width=True,
            disabled=not url
        )
    
    # Área principal
    if analyze_button and url:
        with st.spinner("🔄 Carregando página..."):
            try:
                html_content, final_url = load_page(url, user_agent)
                st.success(f"✅ Página carregada com sucesso!")
                
                if final_url != url:
                    st.info(f"📍 URL final: {final_url}")
                
                # Análises
                with st.spinner("🔍 Analisando estrutura HTML..."):
                    lists_analysis = analyze_lists(html_content)
                    forms_analysis = analyze_forms(html_content)
                    nav_analysis = analyze_navigation(html_content, final_url)
                    content_analysis = analyze_content_structure(html_content)
                
                # Tabs para diferentes análises
                tab1, tab2, tab3, tab4, tab5 = st.tabs([
                    "📋 Listas",
                    "📝 Formulários",
                    "🔗 Navegação",
                    "📄 Conteúdo",
                    "📊 Resumo"
                ])
                
                # =========================
                # TAB 1: LISTAS
                # =========================
                with tab1:
                    st.header("📋 Análise de Listas")
                    
                    # Estatísticas gerais
                    total_lists = sum([
                        len(lists_analysis['navigation_menus']),
                        len(lists_analysis['content_lists']),
                        len(lists_analysis['galleries']),
                        len(lists_analysis['other_lists'])
                    ])
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total de listas", total_lists)
                    with col2:
                        st.metric("Menus de navegação", len(lists_analysis['navigation_menus']))
                    with col3:
                        st.metric("Listas de conteúdo", len(lists_analysis['content_lists']))
                    with col4:
                        st.metric("Galerias", len(lists_analysis['galleries']))
                    
                    st.divider()
                    
                    # Menus de navegação detectados
                    if lists_analysis['navigation_menus']:
                        st.subheader("🧭 Menus de Navegação Detectados")
                        st.caption("Listas onde todos os items têm links e texto curto")
                        
                        for menu in lists_analysis['navigation_menus']:
                            with st.expander(f"Menu com {menu['total_items']} items"):
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    st.markdown("**Informações:**")
                                    st.text(f"Tipo: {menu['type']}")
                                    st.text(f"Container pai: <{menu['parent_tag']}>")
                                    if menu['parent_class']:
                                        st.text(f"Classe do pai: {menu['parent_class']}")
                                    st.text(f"Total de items: {menu['total_items']}")
                                    
                                    st.markdown("**Seletores:**")
                                    st.code(f"CSS: {menu['css_selector']}", language='css')
                                    st.code(f"XPath: {menu['xpath']}", language='xpath')
                                
                                with col2:
                                    st.markdown(f"**Todos os {len(menu['all_items'])} items do menu:**")
                                    for idx, item in enumerate(menu['all_items'], 1):
                                        if item['text']:
                                            # Indica se tem link
                                            link_indicator = "🔗" if item['has_link'] else ""
                                            st.text(f"{idx}. {item['text'][:50]} {link_indicator}")
                                    
                                    if len(menu['all_items']) > 20:
                                        st.info(f"Menu extenso com {len(menu['all_items'])} items")
                                
                                st.markdown("**HTML Sample do menu:**")
                                st.code(menu['html_sample'], language='html')
                                
                                # Mostra HTML de um item como exemplo
                                if menu['all_items'] and menu['all_items'][0].get('html'):
                                    st.markdown("**HTML de um item de exemplo:**")
                                    st.code(menu['all_items'][0]['html'], language='html')
                    
                    # Listas de conteúdo
                    if lists_analysis['content_lists']:
                        st.subheader("📚 Listas de Conteúdo")
                        st.caption("Listas com texto longo, geralmente artigos ou posts")
                        
                        for lst in lists_analysis['content_lists']:
                            with st.expander(f"Lista com {lst['total_items']} items (média {lst['avg_text_length']:.0f} chars)"):
                                col1, col2 = st.columns([1, 2])
                                
                                with col1:
                                    st.markdown("**Seletores:**")
                                    st.code(f"CSS: {lst['css_selector']}", language='css')
                                    st.code(f"XPath: {lst['xpath']}", language='xpath')
                                    
                                    st.markdown("**Características:**")
                                    st.text(f"Total de items: {lst['total_items']}")
                                    st.text(f"Items com links: {lst['items_with_links']}")
                                    st.text(f"Items com imagens: {lst['items_with_images']}")
                                    st.text(f"Container pai: <{lst['parent_tag']}>")
                                    if lst['parent_class']:
                                        st.text(f"Classe do pai: {lst['parent_class']}")
                                
                                with col2:
                                    st.markdown(f"**Todos os {len(lst['all_items'])} items detectados:**")
                                    
                                    # Mostra TODOS os items
                                    for idx, item in enumerate(lst['all_items'], 1):
                                        # Cria um indicador visual do que o item contém
                                        indicators = []
                                        if item['has_link']:
                                            indicators.append("🔗")
                                        if item['has_image']:
                                            indicators.append("🖼️")
                                        
                                        indicator_str = " ".join(indicators)
                                        
                                        # Mostra o texto do item
                                        if item['text']:
                                            # Trunca textos muito longos para não poluir a interface
                                            display_text = item['text'][:200] + "..." if len(item['text']) > 200 else item['text']
                                            st.text(f"{idx}. {display_text} {indicator_str}")
                                        else:
                                            st.text(f"{idx}. [Sem texto] {indicator_str}")
                                    
                                    # Se houver muitos items, adiciona nota
                                    if len(lst['all_items']) > 20:
                                        st.info(f"📊 Lista grande com {len(lst['all_items'])} items totais")
                                
                                st.markdown("**HTML Sample da lista:**")
                                st.code(lst['html_sample'], language='html')
                                
                                # Mostra HTML de alguns items como exemplo
                                if lst['all_items'] and lst['all_items'][0].get('html'):
                                    st.markdown("**HTML do primeiro item:**")
                                    st.code(lst['all_items'][0]['html'], language='html')
                    
                    # Galerias
                    if lists_analysis['galleries']:
                        st.subheader("🖼️ Galerias")
                        st.caption("Listas com predominância de imagens")
                        
                        for gal in lists_analysis['galleries']:
                            with st.expander(f"Galeria com {gal['total_items']} items ({gal['items_with_images']} com imagens)"):
                                col1, col2 = st.columns([1, 2])
                                
                                with col1:
                                    st.markdown("**Seletores:**")
                                    st.code(f"CSS: {gal['css_selector']}", language='css')
                                    st.code(f"XPath: {gal['xpath']}", language='xpath')
                                    
                                    st.markdown("**Estatísticas:**")
                                    st.text(f"Total de items: {gal['total_items']}")
                                    st.text(f"Com imagens: {gal['items_with_images']}")
                                    st.text(f"Com links: {gal['items_with_links']}")
                                    st.text(f"Container: <{gal['parent_tag']}>")
                                
                                with col2:
                                    st.markdown(f"**Todos os {len(gal['all_items'])} items da galeria:**")
                                    
                                    for idx, item in enumerate(gal['all_items'], 1):
                                        indicators = []
                                        if item['has_image']:
                                            indicators.append("🖼️")
                                        if item['has_link']:
                                            indicators.append("🔗")
                                        
                                        indicator_str = " ".join(indicators)
                                        
                                        if item['text']:
                                            display_text = item['text'][:100] + "..." if len(item['text']) > 100 else item['text']
                                            st.text(f"{idx}. {display_text} {indicator_str}")
                                        else:
                                            st.text(f"{idx}. [Item visual] {indicator_str}")
                                
                                st.markdown("**HTML Sample:**")
                                st.code(gal['html_sample'], language='html')
                    
                    # Outras listas
                    if lists_analysis['other_lists']:
                        st.subheader("📝 Outras Listas")
                        st.caption("Listas que não se encaixam nas categorias anteriores")
                        
                        for lst in lists_analysis['other_lists']:
                            with st.expander(f"Lista {lst['type']} com {lst['total_items']} items"):
                                st.markdown("**Seletores:**")
                                st.code(f"CSS: {lst['css_selector']}", language='css')
                                st.code(f"XPath: {lst['xpath']}", language='xpath')
                                
                                st.markdown("**Características:**")
                                st.text(f"Container pai: <{lst['parent_tag']}>")
                                st.text(f"Média de texto: {lst['avg_text_length']:.0f} chars")
                                st.text(f"Items com links: {lst['items_with_links']}")
                                st.text(f"Items com imagens: {lst['items_with_images']}")
                                
                                # Mostra alguns items
                                if lst['all_items']:
                                    st.markdown("**Primeiros items:**")
                                    for idx, item in enumerate(lst['all_items'][:10], 1):
                                        if item['text']:
                                            display_text = item['text'][:150] + "..." if len(item['text']) > 150 else item['text']
                                            st.text(f"{idx}. {display_text}")
                                
                                st.markdown("**HTML Sample:**")
                                st.code(lst['html_sample'], language='html')
                
                # =========================
                # TAB 2: FORMULÁRIOS
                # =========================
                with tab2:
                    st.header("📝 Análise de Formulários e Inputs")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Total de forms", len(forms_analysis['forms']))
                    with col2:
                        st.metric("Inputs standalone", len(forms_analysis['standalone_inputs']))
                    
                    st.divider()
                    
                    # Formulários
                    if forms_analysis['forms']:
                        st.subheader("📋 Formulários Encontrados")
                        
                        for form in forms_analysis['forms']:
                            with st.expander(f"Form: {form['name'] or form['id'] or 'Sem nome'} ({form['input_count']} inputs)"):
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    st.markdown("**Propriedades:**")
                                    st.text(f"Action: {form['action'] or 'N/A'}")
                                    st.text(f"Method: {form['method']}")
                                    st.text(f"ID: {form['id'] or 'N/A'}")
                                    st.text(f"Class: {form['class'] or 'N/A'}")
                                
                                with col2:
                                    st.markdown("**Tipos de input:**")
                                    for inp_type, count in form['input_types'].items():
                                        st.text(f"{inp_type}: {count}")
                                
                                st.markdown("**Seletores:**")
                                st.code(f"CSS: {form['css_selector']}", language='css')
                                st.code(f"XPath: {form['xpath']}", language='xpath')
                                
                                st.markdown("**HTML Sample:**")
                                st.code(form['html_sample'], language='html')
                    
                    # Inputs standalone
                    if forms_analysis['standalone_inputs']:
                        st.subheader("🔤 Inputs Fora de Formulários")
                        
                        for inp in forms_analysis['standalone_inputs'][:10]:
                            with st.expander(f"{inp['tag']} - {inp['name'] or inp['id'] or 'Sem identificação'}"):
                                st.text(f"Type: {inp['type']}")
                                st.text(f"Placeholder: {inp['placeholder'] or 'N/A'}")
                                st.code(f"CSS: {inp['css_selector']}", language='css')
                                st.code(f"XPath: {inp['xpath']}", language='xpath')
                                st.code(inp['html_sample'], language='html')
                
                # =========================
                # TAB 3: NAVEGAÇÃO
                # =========================
                with tab3:
                    st.header("🔗 Análise de Links e Navegação")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Links internos", len(nav_analysis['internal_links']))
                    with col2:
                        st.metric("Links externos", len(nav_analysis['external_links']))
                    with col3:
                        st.metric("Padrões de nav", len(nav_analysis['navigation_patterns']))
                    
                    st.divider()
                    
                    # Padrões de navegação
                    if nav_analysis['navigation_patterns']:
                        st.subheader("🧭 Padrões de Navegação Detectados")
                        st.caption("Containers com múltiplos links agrupados")
                        
                        for tag, pattern in nav_analysis['navigation_patterns'].items():
                            with st.expander(f"Container <{tag}> com {pattern['link_count']} links"):
                                st.markdown("**Links de exemplo:**")
                                for link in pattern['sample_links']:
                                    st.text(f"• {link['text']} → {link['href'][:50]}...")
                    
                    # Sample de links
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("🏠 Links Internos")
                        for link in nav_analysis['internal_links'][:10]:
                            with st.expander(link['text'] or link['href'][:30]):
                                st.text(f"Href: {link['href']}")
                                st.text(f"Parent: <{link['parent_tag']}>")
                                st.code(f"CSS: {link['css_selector']}", language='css')
                                if 'xpath' in link:
                                    st.code(f"XPath: {link['xpath']}", language='xpath')
                                st.code(link['html_sample'], language='html')
                    
                    with col2:
                        st.subheader("🌐 Links Externos")
                        for link in nav_analysis['external_links'][:10]:
                            with st.expander(link['text'] or link['href'][:30]):
                                st.text(f"Href: {link['href']}")
                                st.text(f"Parent: <{link['parent_tag']}>")
                                st.code(f"CSS: {link['css_selector']}", language='css')
                                if 'xpath' in link:
                                    st.code(f"XPath: {link['xpath']}", language='xpath')
                                st.code(link['html_sample'], language='html')
                
                # =========================
                # TAB 4: CONTEÚDO
                # =========================
                with tab4:
                    st.header("📄 Análise de Estrutura de Conteúdo")
                    
                    # Títulos
                    st.subheader("📌 Hierarquia de Títulos")
                    
                    for level, headings in content_analysis['headings'].items():
                        if headings:
                            with st.expander(f"{level.upper()} - {len(headings)} encontrados"):
                                for h in headings[:10]:
                                    st.text(f"• {h['text']}")
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.code(f"CSS: {h['css_selector']}", language='css')
                                    with col2:
                                        if 'xpath' in h:
                                            st.code(f"XPath: {h['xpath']}", language='xpath')
                    
                    # Blocos de conteúdo
                    if content_analysis['content_blocks']:
                        st.subheader("📦 Blocos de Conteúdo Principal")
                        st.caption("Divs e sections com texto substancial")
                        
                        for block in content_analysis['content_blocks'][:10]:
                            with st.expander(f"<{block['tag']}> - {block['text_length']} caracteres"):
                                st.text(f"ID: {block['id'] or 'N/A'}")
                                st.text(f"Class: {block['class'] or 'N/A'}")
                                st.markdown("**Preview do texto:**")
                                st.text(block['text_preview'])
                                st.code(f"CSS: {block['css_selector']}", language='css')
                                if 'xpath' in block:
                                    st.code(f"XPath: {block['xpath']}", language='xpath')
                    
                    # Tabelas
                    if content_analysis['tables']:
                        st.subheader("📊 Tabelas")
                        
                        for table in content_analysis['tables']:
                            with st.expander(f"Tabela: {table['rows']} linhas x {table['cells']} células"):
                                st.text(f"ID: {table['id'] or 'N/A'}")
                                st.text(f"Class: {table['class'] or 'N/A'}")
                                st.code(f"CSS: {table['css_selector']}", language='css')
                                if 'xpath' in table:
                                    st.code(f"XPath: {table['xpath']}", language='xpath')
                                st.code(table['html_sample'], language='html')
                
                # =========================
                # TAB 5: RESUMO
                # =========================
                with tab5:
                    st.header("📊 Resumo da Análise")
                    
                    # Métricas gerais
                    st.subheader("📈 Estatísticas Gerais")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        total_lists = sum([
                            len(lists_analysis['navigation_menus']),
                            len(lists_analysis['content_lists']),
                            len(lists_analysis['galleries']),
                            len(lists_analysis['other_lists'])
                        ])
                        st.metric("Listas", total_lists)
                    
                    with col2:
                        st.metric("Formulários", len(forms_analysis['forms']))
                    
                    with col3:
                        total_links = len(nav_analysis['internal_links']) + len(nav_analysis['external_links'])
                        st.metric("Links", total_links)
                    
                    with col4:
                        total_headings = sum(len(h) for h in content_analysis['headings'].values())
                        st.metric("Títulos", total_headings)
                    
                    st.divider()
                    
                    # Sugestões para crawler
                    st.subheader("💡 Sugestões para Criar um Crawler")
                    
                    suggestions = []
                    
                    # Baseado em menus de navegação
                    if lists_analysis['navigation_menus']:
                        menu = lists_analysis['navigation_menus'][0]
                        suggestions.append(f"**Menu de navegação principal:** Use o seletor `{menu['css_selector']}` para extrair links de navegação")
                    
                    # Baseado em listas de conteúdo
                    if lists_analysis['content_lists']:
                        lst = lists_analysis['content_lists'][0]
                        suggestions.append(f"**Lista de conteúdo:** Use `{lst['css_selector']}` para extrair items de conteúdo (artigos/posts)")
                    
                    # Baseado em formulários
                    if forms_analysis['forms']:
                        suggestions.append(f"**Formulários detectados:** {len(forms_analysis['forms'])} formulários encontrados para possível automação")
                    
                    # Baseado em tabelas
                    if content_analysis['tables']:
                        suggestions.append(f"**Dados tabulares:** {len(content_analysis['tables'])} tabelas encontradas para extração estruturada")
                    
                    # Baseado em padrões de navegação
                    if nav_analysis['navigation_patterns']:
                        suggestions.append(f"**Padrões de navegação:** {len(nav_analysis['navigation_patterns'])} containers com agrupamento de links")
                    
                    if suggestions:
                        for suggestion in suggestions:
                            st.info(suggestion)
                    else:
                        st.warning("Não foram encontrados padrões claros para sugerir")
                    
                    st.divider()
                    
                    # Código de exemplo
                    st.subheader("🔨 Código de Exemplo para Crawler")
                    
                    code_example = f"""
# Exemplo de código para extrair dados desta página
import requests
from lxml import html

url = "{url}"
response = requests.get(url)
doc = html.fromstring(response.content)
"""
                    
                    if lists_analysis['navigation_menus']:
                        code_example += f"""
# Extrair menu de navegação
menu_items = doc.xpath('{lists_analysis['navigation_menus'][0]['xpath']}//li')
for item in menu_items:
    link = item.xpath('.//a/@href')
    text = item.xpath('.//a/text()')
    print(f"{{text}}: {{link}}")
"""
                    
                    if lists_analysis['content_lists']:
                        code_example += f"""
# Extrair lista de conteúdo
content_items = doc.xpath('{lists_analysis['content_lists'][0]['xpath']}//li')
for item in content_items:
    # Processar cada item
    pass
"""
                    
                    st.code(code_example, language='python')
                
            except Exception as e:
                st.error(f"❌ Erro ao analisar página: {str(e)}")
                st.info("💡 Verifique se a URL está correta e acessível")

if __name__ == "__main__":
    main()