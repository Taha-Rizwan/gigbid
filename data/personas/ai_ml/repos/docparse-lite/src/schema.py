"""
Pydantic schema defining the 18 fields expected from each document.
"""

from pydantic import BaseModel, Field, validator
from datetime import date
from typing import Optional

class DocumentFields(BaseModel):
    invoice_number: str = Field(..., description="Unique invoice identifier")
    bill_of_lading: str = Field(..., description="B/L reference")
    shipper_name: str = Field(..., description="Name of the shipper")
    consignee_name: str = Field(..., description="Name of the consignee")
    origin_port: str = Field(..., description="Port of loading")
    destination_port: str = Field(..., description="Port of discharge")
    vessel_name: Optional[str] = Field(None, description="Vessel used")
    departure_date: date = Field(..., description="Date of departure")
    arrival_date: date = Field(..., description="Date of arrival")
    cargo_description: str = Field(..., description="Description of goods")
    gross_weight_kg: float = Field(..., ge=0, description="Total weight in kilograms")
    net_weight_kg: float = Field(..., ge=0, description="Net weight in kilograms")
    container_number: Optional[str] = Field(None, description="Container identifier")
    freight_amount_usd: float = Field(..., ge=0, description="Freight charge")
    insurance_amount_usd: float = Field(..., ge=0, description="Insurance charge")
    total_amount_usd: float = Field(..., ge=0, description="Invoice total")
    payment_terms: str = Field(..., description="Terms of payment")
    notes: Optional[str] = Field(None, description="Additional remarks")

    @validator("arrival_date")
    def arrival_not_before_departure(cls, v, values):
        dep = values.get("departure_date")
        if dep and v < dep:
            raise ValueError("arrival_date cannot be earlier than departure_date")
        return v
