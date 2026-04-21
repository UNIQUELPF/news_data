import trafilatura
from markdownify import markdownify as md
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)

class ContentEngine:
    @staticmethod
    def process(raw_html: str, base_url: str, fallback_selector: str = None) -> dict:
        """
        Process raw HTML to extract cleaned HTML, Markdown, and plain text.
        
        Args:
            raw_html: The original HTML content from the spider.
            base_url: The URL of the article to resolve relative links.
            fallback_selector: Optional CSS selector to use if trafilatura fails.
            
        Returns:
            A dictionary containing:
            - content_cleaned: Cleaned HTML string.
            - content_markdown: Content converted to Markdown.
            - content_plain: Pure text content.
            - images: List of image metadata [{"url": "...", "alt": "..."}].
        """
        # 1. Pre-process: Narrow down HTML to help Trafilatura focus
        try:
            html_to_process = raw_html
            if fallback_selector:
                pre_soup = BeautifulSoup(raw_html, 'lxml')
                content_area = pre_soup.select_one(fallback_selector)
                if content_area:
                    # Wrapping in basic HTML tags helps trafilatura's parser
                    html_to_process = f"<html><body>{str(content_area)}</body></html>"
                    logger.info(f"Refined HTML to fallback_selector area for {base_url}")

            # 2. Try Trafilatura with High Recall, Formatting and Language hint
            extracted_html = trafilatura.extract(
                html_to_process,
                output_format="html",
                include_images=True,
                include_links=True,
                include_tables=True,
                include_formatting=True, # Keep bold, italics, etc.
                include_comments=False,
                favor_recall=True,       # Be more permissive
                target_language='en'     # Help text density calculation
            )

            # 2. Check if we need to switch to Fidelity Mode (BS4 Fallback)
            # We switch if Trafilatura missed images that are present in the fallback area
            use_fidelity_mode = False
            raw_soup = BeautifulSoup(raw_html, 'lxml')
            fallback_area = raw_soup.select_one(fallback_selector) if fallback_selector else None
            
            if fallback_area:
                raw_img_count = len(fallback_area.find_all('img'))
                
                # If trafilatura returned content but significantly fewer images than the main area
                extracted_soup = BeautifulSoup(extracted_html or '', 'lxml')
                extracted_img_count = len(extracted_soup.find_all('img'))
                
                if raw_img_count > 0 and extracted_img_count == 0:
                    logger.info(f"Trafilatura stripped all images. Switching to Fidelity Mode for {base_url}")
                    use_fidelity_mode = True

            # 3. Execution based on mode
            if use_fidelity_mode and fallback_area:
                logger.info(f"Using FIDELITY MODE for {base_url} (Found {raw_img_count} images in fallback)")
                soup = ContentEngine._clean_with_bs4(fallback_area, base_url)
            elif extracted_html:
                logger.info(f"Using SMART MODE for {base_url}")
                soup = BeautifulSoup(extracted_html, 'lxml')
                soup = ContentEngine._clean_with_bs4(soup, base_url)
            else:
                return {"content_cleaned": "", "content_markdown": "", "content_plain": "", "images": []}

            # 4. Final Cleanup & Image Extraction
            images = []
            for img in soup.find_all('img'):
                src = img.get('src')
                if src:
                    alt = img.get('alt', '')
                    images.append({"url": src, "alt": alt})

            content_cleaned = str(soup)
            content_markdown = md(content_cleaned, strip=['script', 'style', 'iframe', 'object', 'embed'])
            content_plain = soup.get_text(separator=' ', strip=True)

            logger.info(f"Extraction complete for {base_url}: {len(images)} images found, {len(content_markdown)} chars Markdown")

            return {
                "content_cleaned": content_cleaned.strip(),
                "content_markdown": content_markdown.strip(),
                "content_plain": content_plain.strip(),
                "images": images
            }
        except Exception as e:
            logger.error(f"Post-processing error for {base_url}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "content_cleaned": "",
                "content_markdown": "",
                "content_plain": "",
                "images": []
            }
    @staticmethod
    def _clean_with_bs4(soup, base_url):
        """
        Helper to clean a BeautifulSoup object: removes noise and normalizes URLs.
        """
        # 1. Remove noise
        for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form', 'button', 'iframe']):
            tag.decompose()

        # 2. Normalize Images
        for img in soup.find_all('img'):
            # Handle lazy loading
            src = img.get('src') or img.get('data-src') or img.get('data-original') or img.get('data-lazy-src')
            if src:
                absolute_src = urljoin(base_url, src)
                img['src'] = absolute_src
                # Clean up other attributes
                alt = img.get('alt', '')
                img.attrs = {'src': absolute_src, 'alt': alt}
            else:
                img.decompose()

        # 3. Normalize Links
        for a in soup.find_all('a'):
            href = a.get('href')
            if href:
                a['href'] = urljoin(base_url, href)
            
            # Clean up other attributes but keep text
            text = a.get_text()
            a.attrs = {'href': a.get('href', '#')}

        return soup
