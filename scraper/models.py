# scraper/models.py
"""
Shared dataclass for a scraped job listing.
Used by all portal scrapers and the orchestrator.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class JobListing:
    """Represents a single scraped job listing from any portal."""
    title: str
    company: str
    location: str
    portal: str                          # 'LinkedIn' | 'Indeed' | 'Rozee.pk'
    url: str

    description: str = ""
    skills_mentioned: List[str] = field(default_factory=list)
    modality: str = "Unknown"            # 'Remote' | 'Hybrid' | 'On-site' | 'Unknown'
    match_score: float = 0.0             # 0–100, set by orchestrator after scraping
    salary: Optional[str] = None
    posted_date: Optional[str] = None
    job_type: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "title":            self.title,
            "company":          self.company,
            "location":         self.location,
            "portal":           self.portal,
            "url":              self.url,
            "description":      self.description,
            "skills_mentioned": self.skills_mentioned,
            "modality":         self.modality,
            "match_score":      self.match_score,
            "salary":           self.salary,
            "posted_date":      self.posted_date,
            "job_type":         self.job_type,
        }