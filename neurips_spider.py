import scrapy
import os
import re


class NeurIPSSpider(scrapy.Spider):
    name = "neurips"
    start_urls = ["https://papers.nips.cc/"]

    target_years = ['2019', '2020', '2021', '2022', '2023']
    download_count = 0
    failed_count = 0

    def parse(self, response):
        """
        Parses the main page and extracts links to yearly conference pages.
        """
        year_links = response.css("div.col-sm ul li a::attr(href)").getall()

        for link in year_links:
            year = re.search(r'\d{4}', link)
            if year and year.group() in self.target_years:
                year = year.group()
                self.logger.info(f"Found year: {year} link: {link}")
                yield response.follow(link, self.parse_conference_list, cb_kwargs={'year': year})

    def parse_conference_list(self, response, year):
        """
        Extracts links to all individual conference pages from the year's list page.
        """
        conference_links = response.css("div.container-fluid div ul li a::attr(href)").getall()

        if conference_links:
            for link in conference_links:
                yield response.follow(link, self.parse_paper_details, cb_kwargs={'year': year})
        else:
            self.logger.error(f"No conferences found for year {year}")

    def parse_paper_details(self, response, year):
        """
        Extracts paper details such as title, authors, and PDF link, then downloads it locally.
        """
        paper_title = response.css("h4::text").get()
        authors = response.css("body > div.container-fluid > div > p:nth-child(6) > i::text").get()

        # Extract PDF link
        pdf_link = None
        for link in response.css("div.container-fluid > div > div > a"):
            if link.css("::text").get() == "Paper":
                pdf_link = response.urljoin(link.css("::attr(href)").get())
                break

        if pdf_link:
            clean_title = self.clean_filename(paper_title or "Unknown_Title")
            clean_authors = self.clean_filename(authors or "Unknown_Authors")
            file_name = f"{clean_title} - {clean_authors}.pdf"
            file_path = os.path.join(f"H:/DataScrappedAsync/{year}", file_name)

            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            self.logger.info(f"Downloading PDF from: {pdf_link}")
            yield response.follow(pdf_link, self.save_pdf, cb_kwargs={'file_path': file_path})
        else:
            self.logger.error(f"No valid PDF link found for '{paper_title}' ({year})")
            self.failed_count += 1

        yield {
            "title": paper_title,
            "authors": authors,
            "pdf_link": pdf_link,
            "year": year,
            "status": "Downloaded" if pdf_link else "Failed"
        }

    def save_pdf(self, response, file_path):
        """
        Saves the PDF using Scrapy's built-in response.body.
        """
        with open(file_path, 'wb') as f:
            f.write(response.body)

        self.download_count += 1
        self.logger.info(f"PDF successfully saved: {file_path}")

    def clean_filename(self, name):
        """
        Cleans up the title and authors to make a valid filename.
        """
        return re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')

    def close(self, reason):
        """
        Called when the spider finishes. Logs the total number of PDFs downloaded and failed attempts.
        """
        self.logger.info(f"Spider finished. {self.download_count} PDFs were downloaded successfully.")
        self.logger.info(f"{self.failed_count} PDFs failed to download.")
