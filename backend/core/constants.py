from django.utils.translation import gettext_lazy as _

COUNTRIES = [
    ('AD', _('Andorra')), ('AE', _('United Arab Emirates')), ('AF', _('Afghanistan')),
    ('AG', _('Antigua and Barbuda')), ('AI', _('Anguilla')), ('AL', _('Albania')),
    ('AM', _('Armenia')), ('AO', _('Angola')), ('AR', _('Argentina')), ('AU', _('Australia')),
    ('AT', _('Austria')), ('AZ', _('Azerbaijan')), ('BA', _('Bosnia and Herzegovina')),
    ('BB', _('Barbados')), ('BD', _('Bangladesh')), ('BE', _('Belgium')), ('BF', _('Burkina Faso')),
    ('BG', _('Bulgaria')), ('BH', _('Bahrain')), ('BI', _('Burundi')), ('BJ', _('Benin')),
    ('BR', _('Brazil')), ('CA', _('Canada')), ('CN', _('China')), ('CO', _('Colombia')),
    ('CR', _('Costa Rica')), ('CU', _('Cuba')), ('DE', _('Germany')), ('DK', _('Denmark')),
    ('DO', _('Dominican Republic')), ('DZ', _('Algeria')), ('EC', _('Ecuador')),
    ('EE', _('Estonia')), ('EG', _('Egypt')), ('ES', _('Spain')), ('FI', _('Finland')),
    ('FR', _('France')), ('GB', _('United Kingdom')), ('GR', _('Greece')),
    ('HU', _('Hungary')), ('ID', _('Indonesia')), ('IE', _('Ireland')),
    ('IN', _('India')), ('IT', _('Italy')), ('JP', _('Japan')), ('KE', _('Kenya')),
    ('KR', _('South Korea')), ('LT', _('Lithuania')), ('LU', _('Luxembourg')),
    ('MX', _('Mexico')), ('NG', _('Nigeria')), ('NL', _('Netherlands')), ('NO', _('Norway')),
    ('NZ', _('New Zealand')), ('PK', _('Pakistan')), ('PL', _('Poland')),
    ('PT', _('Portugal')), ('RU', _('Russia')), ('SA', _('Saudi Arabia')),
    ('SE', _('Sweden')), ('SG', _('Singapore')), ('TH', _('Thailand')),
    ('TR', _('Turkey')), ('UA', _('Ukraine')), ('US', _('United States')),
    ('VN', _('Vietnam')), ('ZA', _('South Africa')), ('ZW', _('Zimbabwe'))
]

CURRENCY = [
    ('USD', _('DOLLAR')),
    ('EUR', _('EURO')),
    ('GBP', _('GREAT BRITAIN POUND'))
]

INDUSTRIES = [
    ('AGRICULTURE', _('Agriculture')),
    ('FISHING', _('Fishing & Aquaculture')),
    ('FORESTRY', _('Forestry & Logging')),
    ('MINING', _('Mining & Quarrying')),
    ('OIL_GAS', _('Oil & Gas')),
    ('UTILITIES', _('Utilities (Water, Electricity, Gas)')),

    ('CONSTRUCTION', _('Construction')),
    ('REAL_ESTATE', _('Real Estate & Property Management')),
    ('ARCHITECTURE', _('Architecture & Planning')),
    ('ENGINEERING', _('Engineering & Design Services')),

    ('MANUFACTURING', _('Manufacturing')),
    ('AUTOMOTIVE', _('Automotive Manufacturing')),
    ('AEROSPACE', _('Aerospace & Defense')),
    ('CHEMICALS', _('Chemicals')),
    ('PHARMACEUTICALS', _('Pharmaceuticals')),
    ('BIOTECHNOLOGY', _('Biotechnology')),
    ('FOOD_BEVERAGE', _('Food & Beverage Manufacturing')),
    ('TEXTILES', _('Textiles & Apparel')),
    ('ELECTRONICS', _('Electronics & Semiconductors')),

    ('WHOLESALE', _('Wholesale Trade')),
    ('RETAIL', _('Retail')),
    ('ECOMMERCE', _('E-commerce')),

    ('TRANSPORTATION', _('Transportation & Logistics')),
    ('WAREHOUSING', _('Warehousing')),
    ('SHIPPING', _('Shipping & Maritime')),
    ('AVIATION', _('Aviation')),

    ('INFORMATION_TECHNOLOGY', _('Information Technology')),
    ('SOFTWARE', _('Software Development')),
    ('SAAS', _('Software as a Service')),
    ('HARDWARE', _('Hardware & Devices')),
    ('CYBERSECURITY', _('Cybersecurity')),
    ('IT_SERVICES', _('IT Services & Consulting')),

    ('TELECOMMUNICATIONS', _('Telecommunications')),
    ('MEDIA', _('Media & Broadcasting')),
    ('ENTERTAINMENT', _('Entertainment')),
    ('GAMING', _('Gaming')),

    ('FINANCIAL_SERVICES', _('Financial Services')),
    ('BANKING', _('Banking')),
    ('INSURANCE', _('Insurance')),
    ('INVESTMENT', _('Investment Management')),
    ('FINTECH', _('Fintech')),

    ('HEALTHCARE', _('Healthcare Services')),
    ('HOSPITALS', _('Hospitals')),
    ('MEDICAL_DEVICES', _('Medical Devices')),
    ('WELLNESS', _('Wellness & Fitness')),

    ('EDUCATION', _('Education')),
    ('EDTECH', _('EdTech')),
    ('RESEARCH', _('Research & Development')),

    ('PUBLIC_SECTOR', _('Public Sector')),
    ('GOVERNMENT', _('Government')),
    ('DEFENSE', _('Defense & Security')),

    ('NONPROFIT', _('Nonprofit & NGOs')),
    ('RELIGIOUS', _('Religious Organizations')),

    ('HOSPITALITY', _('Hospitality')),
    ('TRAVEL_TOURISM', _('Travel & Tourism')),
    ('RESTAURANTS', _('Restaurants & Food Services')),

    ('ARTS_CULTURE', _('Arts & Culture')),
    ('SPORTS', _('Sports & Recreation')),
    ('EVENTS', _('Events & Exhibitions')),

    ('PROFESSIONAL_SERVICES', _('Professional Services')),
    ('LEGAL', _('Legal Services')),
    ('ACCOUNTING', _('Accounting')),
    ('CONSULTING', _('Consulting')),
    ('MARKETING', _('Marketing & Advertising')),
    ('HR', _('Human Resources')),
    ('RECRUITING', _('Recruiting & Staffing')),

    ('ENVIRONMENT', _('Environmental Services')),
    ('WASTE_MANAGEMENT', _('Waste Management')),
    ('RENEWABLE_ENERGY', _('Renewable Energy')),

    ('OTHER', _('Other')),
]