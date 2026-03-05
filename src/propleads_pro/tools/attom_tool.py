"""
ATTOM Property Search Tool
============================
Searches the ATTOM real estate database for motivated seller leads.

NO API KEY?  → runs in MOCK MODE automatically.
              Returns 5 realistic sample leads so you can test
              everything without paying for ATTOM yet.

HAS API KEY? → hits the real ATTOM API and returns live data.
"""

import os, json, requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class AttomInput(BaseModel):
    state:     str = Field(description="2-letter state code: CA, FL, or TX")
    zip_code:  str = Field(default="", description="5-digit ZIP code")
    min_dom:   int = Field(default=45,      description="Min days on market")
    min_price: int = Field(default=500000,  description="Min list price $")
    max_price: int = Field(default=2000000, description="Max list price $")


# ── Realistic mock data (used when ATTOM_API_KEY is missing) ──

MOCK_LEADS = [
    {
        "address": "1842 Sycamore Canyon Rd", "city": "Austin",
        "state": "TX", "zip": "78701",
        "list_price": 875000, "original_price": 975000,
        "days_on_market": 91, "price_reductions": 2,
        "is_fsbo": False, "pre_foreclosure": True,
        "listing_language": "motivated seller, must close before end of quarter, as-is",
        "seller_email": None, "seller_phone": None,
        "listing_url": "https://zillow.com/homedetails/mock-1", "source": "mock"
    },
    {
        "address": "3317 Palm Grove Ave", "city": "Orlando",
        "state": "FL", "zip": "32801",
        "list_price": 620000, "original_price": 689000,
        "days_on_market": 73, "price_reductions": 3,
        "is_fsbo": True, "pre_foreclosure": False,
        "listing_language": "price reduced again, relocating for work, priced to sell",
        "seller_email": "owner@gmail.com", "seller_phone": "407-555-0182",
        "listing_url": "https://zillow.com/homedetails/mock-2", "source": "mock"
    },
    {
        "address": "9201 Coastal Bluff Dr", "city": "San Diego",
        "state": "CA", "zip": "92101",
        "list_price": 1340000, "original_price": 1490000,
        "days_on_market": 58, "price_reductions": 1,
        "is_fsbo": False, "pre_foreclosure": False,
        "listing_language": "estate sale, court approval required, bring all offers",
        "seller_email": None, "seller_phone": None,
        "listing_url": "https://zillow.com/homedetails/mock-3", "source": "mock"
    },
    {
        "address": "744 Magnolia Terrace", "city": "Tampa",
        "state": "FL", "zip": "33601",
        "list_price": 540000, "original_price": 615000,
        "days_on_market": 112, "price_reductions": 4,
        "is_fsbo": True, "pre_foreclosure": True,
        "listing_language": "divorce sale, must sell immediately, vacant, all offers considered",
        "seller_email": "tampa_seller@gmail.com", "seller_phone": "813-555-0291",
        "listing_url": "https://zillow.com/homedetails/mock-4", "source": "mock"
    },
    {
        "address": "2288 Ridgeline Pass", "city": "Austin",
        "state": "TX", "zip": "78702",
        "list_price": 760000, "original_price": 799000,
        "days_on_market": 67, "price_reductions": 2,
        "is_fsbo": False, "pre_foreclosure": False,
        "listing_language": "seller relocating overseas, quick close preferred",
        "seller_email": None, "seller_phone": None,
        "listing_url": "https://zillow.com/homedetails/mock-5", "source": "mock"
    },
]


class AttomTool(BaseTool):
    name:        str = "ATTOM Property Search"
    description: str = (
        "Search the ATTOM real estate database for motivated seller leads. "
        "Filters by ZIP code, days on market, and price range. "
        "Returns a JSON array of property records."
    )
    args_schema: type[BaseModel] = AttomInput

    def _run(self, state: str, zip_code: str = "",
             min_dom: int = 45, min_price: int = 500000,
             max_price: int = 2000000) -> str:

        api_key = os.getenv("ATTOM_API_KEY")

        # ── NO API KEY → mock mode ─────────────────────────
        if not api_key:
            results = [
                lead for lead in MOCK_LEADS
                if (not zip_code or lead["zip"] == zip_code)
                and lead["days_on_market"] >= min_dom
                and min_price <= lead["list_price"] <= max_price
            ]
            if not results:
                results = MOCK_LEADS[:3]   # always return something
            print(f"   [AttomTool] MOCK MODE — returning {len(results)} sample leads")
            return json.dumps(results)

        # ── REAL ATTOM API ─────────────────────────────────
        params = {
            "propertytype":    "SFR",
            "listingStatus":   "Active",
            "daysOnMarketMin": min_dom,
            "listingPriceMin": min_price,
            "listingPriceMax": max_price,
            "pageSize":        25,
        }
        if zip_code:
            params["postalcode"] = zip_code
        else:
            params["state"] = state

        try:
            resp = requests.get(
                "https://api.gateway.attomdata.com/propertyapi/v1.0.0/sale/snapshot",
                headers={"apikey": api_key, "Accept": "application/json"},
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            props = resp.json().get("property", [])

            leads = []
            for p in props:
                a = p.get("address", {})
                s = p.get("sale", {})
                leads.append({
                    "address":          a.get("line1", ""),
                    "city":             a.get("locality", ""),
                    "state":            a.get("countrySubd", state),
                    "zip":              a.get("postal1", zip_code),
                    "list_price":       s.get("amount", {}).get("saleAmt", 0),
                    "original_price":   s.get("amount", {}).get("saleAmt", 0),
                    "days_on_market":   s.get("daysOnMarket", 0),
                    "price_reductions": 0,
                    "is_fsbo":          False,
                    "pre_foreclosure":  False,
                    "listing_language": "",
                    "seller_email":     None,
                    "seller_phone":     None,
                    "listing_url":      "",
                    "source":           "attom",
                })
            return json.dumps(leads)

        except Exception as e:
            print(f"   [AttomTool] API error: {e} — falling back to mock")
            return json.dumps(MOCK_LEADS[:3])
