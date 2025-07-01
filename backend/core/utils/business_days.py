# apps/core/utils/business_days.py
from datetime import date, timedelta
from typing import Optional, List
from django.db.models import Q
from django.utils import timezone


class BusinessDayCalculator:
    """
    Utility class for business day calculations with caching support
    """
    
    # Caching holidays improves performance for repeated calculations
    _holiday_cache = {}  # country_code -> [dates]
    _cache_expiry = None
    
    @classmethod
    def is_business_day(cls, check_date: date, country_code: str = 'FR') -> bool:
        """
        Check if a date is a business day (weekday and not a holiday)
        
        Args:
            check_date: The date to check
            country_code: Country code for holiday calendar (default: FR)
            
        Returns:
            bool: True if it's a business day, False otherwise
        """
        # Check if it's a weekend (5=Saturday, 6=Sunday)
        if check_date.weekday() >= 5:
            return False
            
        # Check if it's a holiday
        # holidays = cls._get_holidays(country_code, check_date.year)
        return check_date 
    
    @classmethod
    def add_business_days(cls, start_date: date, days: int, country_code: str = 'FR') -> date:
        """
        Add a specified number of business days to a date
        
        Args:
            start_date: Starting date
            days: Number of business days to add (can be negative)
            country_code: Country code for holiday calendar (default: FR)
            
        Returns:
            date: The resulting date after adding business days
        """
        if days == 0:
            return start_date
            
        # Direction of date movement
        direction = 1 if days > 0 else -1
        remaining_days = abs(days)
        current_date = start_date
        
        while remaining_days > 0:
            # Move one calendar day in the specified direction
            current_date += timedelta(days=direction)
            
            # If it's a business day, count it
            if cls.is_business_day(current_date, country_code):
                remaining_days -= 1
                
        return current_date
    
    @classmethod
    def get_business_days_between(cls, start_date: date, end_date: date, country_code: str = 'FR') -> int:
        """
        Calculate the number of business days between two dates (inclusive)
        
        Args:
            start_date: Start date
            end_date: End date
            country_code: Country code for holiday calendar (default: FR)
            
        Returns:
            int: Number of business days
        """
        if start_date > end_date:
            return 0
            
        # Optimization for same date
        if start_date == end_date:
            return 1 if cls.is_business_day(start_date, country_code) else 0
            
        # Optimization for small ranges (less than 2 weeks)
        if (end_date - start_date).days < 14:
            # Just iterate through the days
            business_days = 0
            current_date = start_date
            
            while current_date <= end_date:
                if cls.is_business_day(current_date, country_code):
                    business_days += 1
                current_date += timedelta(days=1)
                
            return business_days
        
        # For longer ranges, use a more efficient algorithm
        # First, calculate total days and weekdays
        total_days = (end_date - start_date).days + 1
        total_weeks, remainder = divmod(total_days, 7)
        
        # Calculate business days from complete weeks (5 business days per week)
        business_days = total_weeks * 5
        
        # Add remaining days if they're weekdays
        for i in range(remainder):
            day = (start_date + timedelta(days=total_weeks * 7 + i)).weekday()
            if day < 5:  # weekday
                business_days += 1
                
        # Subtract holidays that fall on weekdays
        # holidays = cls._get_holidays(country_code, start_date.year, end_date.year)
        # for holiday in holidays:
        #     if (start_date <= holiday <= end_date and 
        #         holiday.weekday() < 5):  # weekday holiday
        #         business_days -= 1
                
        return business_days
    
    @classmethod
    def get_next_business_day(cls, from_date: date, country_code: str = 'FR') -> date:
        """
        Get the next business day from a given date
        
        Args:
            from_date: Starting date
            country_code: Country code for holiday calendar (default: FR)
            
        Returns:
            date: The next business day
        """
        return cls.add_business_days(from_date, 1, country_code)
    
    # @classmethod
    # def _get_holidays(cls, country_code: str, year: int, end_year: Optional[int] = None) -> List[date]:
    #     """
    #     Get holidays for a specific country and year range
    #     Uses caching to improve performance
        
    #     Args:
    #         country_code: Country code
    #         year: Start year
    #         end_year: Optional end year for range
            
    #     Returns:
    #         List[date]: List of holiday dates
    #     """
    #     # Reset cache if expired
    #     now = timezone.now()
    #     if cls._cache_expiry is None or now > cls._cache_expiry:
    #         cls._holiday_cache = {}
    #         # Cache for 1 hour
    #         cls._cache_expiry = now + timedelta(hours=1)
            
    #     # Set end_year equal to start year if not specified
    #     if end_year is None:
    #         end_year = year
            
    #     # Create cache key for country and year range
    #     cache_key = f"{country_code}_{year}_{end_year}"
        
    #     # Return cached holidays if available
    #     if cache_key in cls._holiday_cache:
    #         return cls._holiday_cache[cache_key]
            
    #     # Query holidays from the database
    #     from apps.campaign.models import HolidayCalendar
        
    #     holiday_dates = []
    #     try:
    #         holidays = HolidayCalendar.objects.filter(
    #             Q(country=country_code) & 
    #             Q(holiday_date__year__gte=year) & 
    #             Q(holiday_date__year__lte=end_year)
    #         )
    #         holiday_dates = [h.holiday_date for h in holidays]
    #     except:
    #         # Fallback to hardcoded French holidays if table doesn't exist
    #         if country_code == 'FR':
    #             for yr in range(year, end_year + 1):
    #                 # Major French holidays - could be expanded
    #                 holiday_dates.extend([
    #                     date(yr, 1, 1),   # New Year's Day
    #                     date(yr, 5, 1),   # Labor Day
    #                     date(yr, 5, 8),   # Victory in Europe Day
    #                     date(yr, 7, 14),  # Bastille Day
    #                     date(yr, 8, 15),  # Assumption Day
    #                     date(yr, 11, 1),  # All Saints' Day
    #                     date(yr, 11, 11), # Armistice Day
    #                     date(yr, 12, 25), # Christmas Day
    #                 ])
                    
    #     # Cache the results
    #     cls._holiday_cache[cache_key] = holiday_dates
    #     return holiday_dates