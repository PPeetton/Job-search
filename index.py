# app.py (Flask backend)

from flask import Flask, render_template, jsonify, request
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import csv
import io
from geopy.geocoders import Nominatim
import re
import dateparser
from datetime import datetime
from linkedin_jobs_scraper import LinkedinScraper
from linkedin_jobs_scraper.events import Events, EventData
from linkedin_jobs_scraper.query import Query, QueryOptions
from typing import List, Dict

def convert_date(relative_time):
    parsed_date = dateparser.parse(relative_time)
    return parsed_date.strftime("%Y-%m-%d") if parsed_date else None

def convert_full_date(date_str):
    today = datetime.today()
    
    parsed_date = dateparser.parse(date_str, settings={'PREFER_DATES_FROM': 'past'})
    
    if not parsed_date:
        return None 

    if parsed_date.month > today.month:
        year = today.year - 1 
    else:
        year = today.year  

    final_date = parsed_date.replace(year=year).strftime("%d-%m-%Y")
    return final_date

def get_lat_long(location):
    geolocator = Nominatim(user_agent="geo_locator")
    location_data = geolocator.geocode(location)
    
    if location_data:
        return location_data.latitude, location_data.longitude
    else:
        return None

def encode_for_url(text: str) -> str:
    return re.sub(r', |,| ', '%2C', text)

def get_ziprecruiter_domain(country_iso_code):
    if country_iso_code == 'in':
        return 'ziprecruiter.in'
    elif country_iso_code == 'ca':
        return 'ziprecruiter.ca'
    elif country_iso_code == 'sg':
        return 'ziprecruiter.sg'
    elif country_iso_code == 'ar':
        return 'ziprecruiter.com.ar'
    elif country_iso_code == 'au':
        return 'ziprecruiter.com.au'
    elif country_iso_code == 'ch':
        return 'ziprecruiter.ch'
    elif country_iso_code == 'uk':
        return 'ziprecruiter.co.uk'
    else:
        return 'ziprecruiter.in'

app = Flask(__name__)

def init_driver():
    options = Options()
    options.add_argument("--headless") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(options=options)
    return driver

def scrape_ziprecruiter(job_title, location, num_jobs, jobCountry):
    driver = init_driver()
    rev_geo = get_lat_long(location=location)
    ziprecruiter_url = encode_for_url(f"https://{get_ziprecruiter_domain(jobCountry)}/jobs/search?d=&l={location}&lat={round(rev_geo[0], 2)}&long={round(rev_geo[1], 2)}&page=1&q={job_title}")
    driver.get(ziprecruiter_url)
    result = []
    page_num = 1
    
    while len(result) < num_jobs:
        try:
            # Build the URL for the current page
            
            # Locate the job listing container
            job_container = driver.find_element(By.CLASS_NAME, 'jobList')
            job_cards = job_container.find_elements(By.CLASS_NAME, 'job-listing')
            
            if not job_cards:  # If no jobs are found, break the loop
                return result
                
            # Loop through the job cards and extract the required information
            for job_card in job_cards:
                title = job_card.find_element(By.CLASS_NAME,"jobList-title").text
                href = job_card.find_element(By.CLASS_NAME,"jobList-title").get_attribute("href")
                introMeta = job_card.find_element(By.CLASS_NAME,"jobList-introMeta")
                li = introMeta.find_elements(By.TAG_NAME, "li")
                company = li[0].text
                job_loc = li[1].text
                description = job_card.find_element(By.CLASS_NAME,"jobList-description").text
                date = job_card.find_element(By.CLASS_NAME,"jobList-date").text
                result.append({
                    "title":title,
                    "company":company,
                    "location":job_loc,
                    "description":description,
                    "link":href,
                    'source':'ZipRecruiter',
                    "date":convert_full_date(date)
                })
                
                if len(result) >= num_jobs:
                    break

            page_num += 1  
        
        except Exception as e:
            print(f"An exception occurred: {e}")
            return result  

        try:
            next_button = driver.find_element(By.CLASS_NAME, "pagination").find_elements(By.TAG_NAME, "li")[-1]
            driver.execute_script("arguments[0].click();", next_button)
            time.sleep(3)
        except:
            print("No more pages available.")
            break
    return result

def scrape_indeed(job_title, location, num_jobs, job_url):
    driver = init_driver()
    print(job_url)
    print(num_jobs)
    driver.get(job_url)

    driver.find_element(By.ID, 'text-input-what').send_keys(job_title)
    driver.find_element(By.ID, 'text-input-where').clear()
    driver.find_element(By.ID, 'text-input-where').send_keys(location)
    driver.find_element(By.XPATH, '//button[@type="submit"]').click()

    jobs = []
    while len(jobs) < num_jobs:
        job_cards = driver.find_elements(By.CLASS_NAME, 'job_seen_beacon')
        for card in job_cards:
            try:
                title = card.find_element(By.CLASS_NAME, 'jobTitle').text
                href = card.find_element(By.CLASS_NAME, 'jobTitle').find_element(By.TAG_NAME, 'a').get_attribute("href")
                location = card.find_element(By.CSS_SELECTOR, '[data-testid="text-location"]').text
                job_snippet_footer = card.find_element(By.CSS_SELECTOR, '[data-testid="jobsnippet_footer"]')
                li_elements = job_snippet_footer.find_elements(By.TAG_NAME, "li")
                description = " ".join([li.text for li in li_elements])
                company_name = card.find_element(By.CSS_SELECTOR, '[data-testid="company-name"]').text
                active_date = None
                try:
                    active_date = card.find_element(By.XPATH, '//*[@data-testid="myJobsStateDate"]').text | None
                except:
                    active_date = None
                date = ""
                if active_date is not None:
                    date = convert_date(active_date.replace("Employer", "").replace("Active", ""))


                jobs.append({
                    'title': title,
                    'company': company_name,
                    'location': location,
                    'description': description,
                    'link': href,
                    'source':'Indeed',
                    'date': date
                })

                if len(jobs) >= num_jobs:
                    break
            except Exception as e:
                print(f"Error extracting job info: {e}")

        try:
            next_button = driver.find_element(By.XPATH, '//a[@aria-label="Next Page"]')
            driver.execute_script("arguments[0].click();", next_button)
            time.sleep(3)
        except:
            print("No more pages available.")
            break

    driver.quit()
    return jobs

def scrape_linkedin_jobs(job_title: str, location: str, max_results: int = 10) -> List[Dict]:
    res = []
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--disable-gpu")  # Disable GPU acceleration
    chrome_options.add_argument("--no-sandbox")  # Required for running as root
    chrome_options.add_argument("--disable-dev-shm-usage")
        
    def on_data(data: EventData):
        if len(res) >= max_results:
            scraper.emit(Events.END)
            return
        res.append({
            "title": data.title,
            "company": data.company,
            "location": data.place,
            "description": data.description[:200],  # Limiting description length
            "date": data.date,
            "link": data.link,
            "source": "LinkedIn"
        })

    def on_end():
        print(f"Scraped {len(res)} jobs.")

    scraper = LinkedinScraper(
        chrome_executable_path=None,
        chrome_binary_location=None,
        chrome_options=chrome_options,
        headless=True,
        max_workers=1,
        slow_mo=0.5,
        page_load_timeout=40
    )

    # Add event listeners
    scraper.on(Events.DATA, on_data)
    scraper.on(Events.END, on_end)

    # Define search query
    queries = [
        Query(
            query=job_title,
            options=QueryOptions(
                locations=[location],
                apply_link=True,
                skip_promoted_jobs=True,
                page_offset=0,
            )
        ),
    ]

    # Run the scraper
    scraper.run(queries)

    return res



@app.route('/search_jobs', methods=['GET'])
def search_jobs():
    job_title = request.args.get('job_title')
    location = request.args.get('location')
    num_jobs = int(request.args.get('num_jobs') or "0")
    job_url = request.args.get("job_url")
    job_sources = request.args.get("job_source").split(",")
    job_country = request.args.get("job_country")
    print(job_sources)
    
    num_sources = len(job_sources)
    jobs_per_source = num_jobs // num_sources  
    
    results = []  
    
    if "Indeed" in job_sources:
        indeed_jobs = scrape_indeed(job_title, location, jobs_per_source, job_url)
        results.extend(indeed_jobs)

    if "ZipRecruiter" in job_sources:
        zip_jobs = scrape_ziprecruiter(job_title, location, jobs_per_source, job_country)
        results.extend(zip_jobs)
    
    if "LinkedIn" in job_sources:
        linkedin_jobs = scrape_linkedin_jobs(job_title, location, jobs_per_source)
        results.extend(linkedin_jobs)

    return jsonify(results)


# API to download CSV
@app.route('/download_csv', methods=['GET'])
def download_csv():
    job_title = request.args.get('job_title')
    location = request.args.get('location')
    num_jobs = int(request.args.get('num_jobs') or "0")
    job_url = int(request.args.get('job_url'))
    job_sources = request.args.get("job_source").split(",")
    job_country = request.args.get("job_country")

    num_sources = len(job_sources)
    jobs_per_source = num_jobs // num_sources 
    
    results = []  
    print(job_sources)
    
    if "Indeed" in job_sources:
        indeed_jobs = scrape_indeed(job_title, location, jobs_per_source, job_url)
        results.extend(indeed_jobs)

    if "ZipRecruiter" in job_sources:
        zip_jobs = scrape_ziprecruiter(job_title, location, jobs_per_source, job_country)
        results.extend(zip_jobs)
    
    if "LinkedIn" in job_sources:
        linkedin_jobs = scrape_linkedin_jobs(job_title, location, jobs_per_source)
        results.extend(linkedin_jobs)

    jobs = results


    si = io.StringIO()
    writer = csv.DictWriter(si, fieldnames=['title', 'company', 'location', 'description', 'link', 'source'])
    writer.writeheader()
    writer.writerows(jobs)
    output = si.getvalue()

    response = app.response_class(
        response=output,
        status=200,
        mimetype='text/csv'
    )

    response.headers["Content-Disposition"] = "attachment; filename=jobs.csv"
    return response

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
