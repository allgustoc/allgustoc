from datetime import date

from radar.models import FareKind
from radar.providers.azul import parse_azul
from radar.providers.latam import parse_latam
from radar.providers.seats_aero import parse_seats_aero
from radar.providers.serpapi import parse_google_flights
from radar.providers.smiles import parse_smiles, search_url

DAY = date(2027, 3, 2)


def test_parse_smiles_picks_cheapest_eligible_fare():
    payload = {
        "requestedFlightSegmentList": [{
            "type": "SEGMENT_1",
            "flightList": [{
                "uid": "f1", "stops": 1, "availableSeats": 4,
                "departure": {"date": "2027-03-02T22:10:00", "airport": {"code": "GRU"}},
                "arrival": {"date": "2027-03-03T14:30:00", "airport": {"code": "LIS"}},
                "airline": {"code": "AF", "name": "AIR FRANCE"},
                "duration": {"hours": 13, "minutes": 20},
                "legList": [{"flightNumber": "459", "marketingAirline": {"code": "AF"}},
                            {"flightNumber": "1024", "marketingAirline": {"code": "AF"}}],
                "fareList": [
                    {"uid": "a", "type": "SMILES_CLUB", "miles": 70000, "money": 0},
                    {"uid": "b", "type": "SMILES", "miles": 82000, "money": 0},
                    {"uid": "c", "type": "SMILES_MONEY_CLUB", "miles": 30000, "money": 1500.0},
                ],
            }],
        }]
    }
    (quote, ids), = parse_smiles(payload, DAY, "economy", club=False)
    assert quote.miles == 82000 and ids["fare_uid"] == "b"
    assert quote.kind == FareKind.MILES and quote.program == "smiles"
    assert (quote.origin, quote.destination, quote.stops) == ("GRU", "LIS", 1)
    assert quote.duration_min == 800 and quote.departure_time == "22:10"
    assert quote.flight_numbers == "AF459, AF1024"
    (club_quote, _), = parse_smiles(payload, DAY, "economy", club=True)
    assert club_quote.miles == 70000


def test_smiles_search_url_has_route():
    url = search_url("GRU", "LIS", DAY, 2, "economy")
    assert "originAirport=GRU" in url and "destination=LIS" in url and "adults=2" in url


def test_parse_latam_cash_and_points():
    item = {
        "summary": {
            "flightCode": "LA8084", "stopOvers": 0, "duration": 650,
            "origin": {"iataCode": "GRU", "departure": "2027-03-02T23:35:00"},
            "destination": {"iataCode": "LIS", "arrival": "2027-03-03T13:25:00"},
            "lowestPrice": {"amount": 3200.5, "currency": "BRL"},
        },
        "itinerary": [{"flight": {"airlineCode": "LA", "flightNumber": 8084}}],
    }
    (q,) = parse_latam({"content": [item]}, DAY, "economy", redemption=False, tax_estimate=400)
    assert q.kind == FareKind.CASH and q.price_brl == 3200.5 and q.flight_numbers == "LA8084"
    award_item = {**item, "summary": {**item["summary"], "lowestPrice": {"amount": 55000, "currency": "LATAM_PASS",
                                                                         "taxes": {"amount": 410.2}}}}
    (a,) = parse_latam({"content": [award_item]}, DAY, "economy", redemption=True, tax_estimate=400)
    assert a.program == "latampass" and a.miles == 55000 and a.taxes_brl == 410.2 and not a.taxes_estimated
    no_tax = {**item, "summary": {**item["summary"], "lowestPrice": {"amount": 55000}}}
    (b,) = parse_latam({"content": [no_tax]}, DAY, "economy", redemption=True, tax_estimate=400)
    assert b.taxes_estimated and b.taxes_brl == 400


def test_parse_azul_points():
    payload = {"data": {"trips": [{"journeys": [{
        "identifier": {"carrierCode": "AD", "flightNumber": "8750", "departureStation": "VCP",
                       "arrivalStation": "LIS", "std": "2027-03-02T17:50:00", "sta": "2027-03-03T07:30:00"},
        "segments": [{}],
        "fares": [{"paxPoints": [{"points": {"amount": 98000}}], "taxes": 350.0},
                  {"paxPoints": [{"points": {"amount": 120000}}]}],
    }]}]}}
    (q,) = parse_azul(payload, DAY, "economy", points=True, tax_estimate=400)
    assert (q.origin, q.destination, q.miles, q.taxes_brl, q.stops) == ("VCP", "LIS", 98000, 350.0, 0)
    assert q.flight_numbers == "AD8750" and q.departure_time == "17:50"


def test_parse_google_flights():
    payload = {
        "search_metadata": {"google_flights_url": "https://g.co/x"},
        "best_flights": [{
            "price": 4100, "total_duration": 760,
            "flights": [
                {"airline": "TAP Air Portugal", "flight_number": "TP 82",
                 "departure_airport": {"id": "GRU", "time": "2027-03-02 16:05"},
                 "arrival_airport": {"id": "LIS", "time": "2027-03-03 05:40"}},
            ],
        }],
        "other_flights": [{"price": 3500, "flights": [
            {"airline": "Iberia", "flight_number": "IB 6826", "departure_airport": {"time": "2027-03-02 18:00"}},
            {"airline": "Iberia", "flight_number": "IB 3102", "arrival_airport": {"time": "2027-03-03 14:00"}},
        ]}],
    }
    quotes = parse_google_flights(payload, "GRU", "LIS", DAY, "economy")
    assert [q.price_brl for q in quotes] == [4100, 3500]
    assert quotes[1].stops == 1 and quotes[1].airline == "Iberia" and quotes[1].arrival_time == "14:00"
    assert quotes[0].booking_url == "https://g.co/x"


def test_parse_seats_aero_converts_taxes():
    payload = {"data": [
        {"Date": "2027-03-02", "Route": {"OriginAirport": "GRU", "DestinationAirport": "LIS", "Source": "smiles"},
         "YAvailable": True, "YMileageCost": "75000", "YTotalTaxes": 9550, "TaxesCurrency": "USD",
         "YDirect": False, "YAirlines": "TP", "YRemainingSeats": 3},
        {"Date": "2027-03-03", "Route": {"OriginAirport": "GRU", "DestinationAirport": "LIS", "Source": "azul"},
         "YAvailable": False, "YMileageCost": "0"},
    ]}
    (q,) = parse_seats_aero(payload, "economy", {"USD": 5.0, "BRL": 1.0})
    assert q.program == "smiles" and q.miles == 75000 and q.taxes_brl == 477.5 and q.stops == 1 and q.seats == 3
