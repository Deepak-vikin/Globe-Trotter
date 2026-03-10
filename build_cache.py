import urllib.request
import urllib.parse
import json
import hashlib

query = """
SELECT ?item ?itemLabel ?lat ?lon ?sitelinks ?image ?stateLabel WHERE {
  ?item wdt:P31/wdt:P279* wd:Q515. 
  ?item wdt:P17 wd:Q668. 
  ?item p:P625 ?coordinate.
  ?coordinate psv:P625 ?coordinate_node.
  ?coordinate_node wikibase:geoLatitude ?lat.
  ?coordinate_node wikibase:geoLongitude ?lon.
  OPTIONAL { ?item wdt:P18 ?image. }
  OPTIONAL {
    ?item wdt:P131 ?state.
    ?state wdt:P31/wdt:P279* wd:Q13212489.
  }
  ?item wikibase:sitelinks ?sitelinks.
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
ORDER BY DESC(?sitelinks)
LIMIT 300
"""

url = "https://query.wikidata.org/sparql?format=json"
req = urllib.request.Request(url, data=query.encode('utf-8'), headers={
    'Accept': 'application/json', 
    'User-Agent': 'GlobeTrotterHelper/1.0', 
    'Content-Type': 'application/sparql-query'
})
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())

spots = []
seen = set()

# Known correct state mapping for major Indian cities (fallback)
CITY_STATE_MAP = {
    "Mumbai": "Maharashtra",
    "New Delhi": "Delhi",
    "Delhi": "Delhi",
    "Kolkata": "West Bengal",
    "Bengaluru": "Karnataka",
    "Bangalore": "Karnataka",
    "Chennai": "Tamil Nadu",
    "Ahmedabad": "Gujarat",
    "Jaipur": "Rajasthan",
    "Hyderabad": "Telangana",
    "Agra": "Uttar Pradesh",
    "Varanasi": "Uttar Pradesh",
    "Pune": "Maharashtra",
    "Lucknow": "Uttar Pradesh",
    "Bhopal": "Madhya Pradesh",
    "Chandigarh": "Punjab/Haryana",
    "Patna": "Bihar",
    "Amritsar": "Punjab",
    "Prayagraj": "Uttar Pradesh",
    "Surat": "Gujarat",
    "Kochi": "Kerala",
    "Kanpur": "Uttar Pradesh",
    "Thiruvananthapuram": "Kerala",
    "Bhubaneswar": "Odisha",
    "Nagpur": "Maharashtra",
    "Indore": "Madhya Pradesh",
    "Agartala": "Tripura",
    "Gangtok": "Sikkim",
    "Madurai": "Tamil Nadu",
    "Mysore": "Karnataka",
    "Mysuru": "Karnataka",
    "Srinagar": "Jammu & Kashmir",
    "Guwahati": "Assam",
    "Visakhapatnam": "Andhra Pradesh",
    "Raipur": "Chhattisgarh",
    "Gwalior": "Madhya Pradesh",
    "Dehradun": "Uttarakhand",
    "Shimla": "Himachal Pradesh",
    "Ranchi": "Jharkhand",
    "Jodhpur": "Rajasthan",
    "Darjeeling": "West Bengal",
    "Vadodara": "Gujarat",
    "Aizawl": "Mizoram",
    "Shillong": "Meghalaya",
    "Ajmer": "Rajasthan",
    "Nashik": "Maharashtra",
    "Coimbatore": "Tamil Nadu",
    "Mangaluru": "Karnataka",
    "Mangalore": "Karnataka",
    "Ludhiana": "Punjab",
    "Imphal": "Manipur",
    "Aurangabad": "Maharashtra",
    "Gandhinagar": "Gujarat",
    "Kozhikode": "Kerala",
    "Vijayawada": "Andhra Pradesh",
    "Panaji": "Goa",
    "Fatehpur Sikri": "Uttar Pradesh",
    "Meerut": "Uttar Pradesh",
    "Udaipur": "Rajasthan",
    "Dharamshala": "Himachal Pradesh",
    "Jabalpur": "Madhya Pradesh",
    "Jamshedpur": "Jharkhand",
    "Faridabad": "Haryana",
    "Srivijayapuram": "Andaman & Nicobar Islands",
    "Itanagar": "Arunachal Pradesh",
    "Aligarh": "Uttar Pradesh",
    "Jalandhar": "Punjab",
    "Ujjain": "Madhya Pradesh",
    "Ghaziabad": "Uttar Pradesh",
    "Tiruchirappalli": "Tamil Nadu",
    "Howrah": "West Bengal",
    "Thane": "Maharashtra",
    "Rajkot": "Gujarat",
    "Kohima": "Nagaland",
    "Ayodhya": "Uttar Pradesh",
    "Bikaner": "Rajasthan",
    "Leh": "Ladakh",
    "Jhansi": "Uttar Pradesh",
    "Puri": "Odisha",
    "Dispur": "Assam",
    "Haridwar": "Uttarakhand",
    "Navi Mumbai": "Maharashtra",
    "Gaya": "Bihar",
    "Tirupati": "Andhra Pradesh",
    "Rishikesh": "Uttarakhand",
    "Tirunelveli": "Tamil Nadu",
    "Agra": "Uttar Pradesh",
    "Daman": "Dadra & Nagar Haveli and Daman & Diu",
    "Silvassa": "Dadra & Nagar Haveli and Daman & Diu",
    "Kavaratti": "Lakshadweep",
    "Puducherry": "Puducherry",
    "Pondicherry": "Puducherry",
    "Salem": "Tamil Nadu",
    "Vellore": "Tamil Nadu",
    "Erode": "Tamil Nadu",
    "Tiruppur": "Tamil Nadu",
    "Warangal": "Telangana",
    "Karimnagar": "Telangana",
    "Nellore": "Andhra Pradesh",
    "Kurnool": "Andhra Pradesh",
    "Guntur": "Andhra Pradesh",
    "Thrissur": "Kerala",
    "Kollam": "Kerala",
    "Kannur": "Kerala",
    "Palakkad": "Kerala",
    "Alappuzha": "Kerala",
    "Durgapur": "West Bengal",
    "Asansol": "West Bengal",
    "Siliguri": "West Bengal",
    "Cuttack": "Odisha",
    "Rourkela": "Odisha",
    "Bilaspur": "Chhattisgarh",
    "Bhillai": "Chhattisgarh",
    "Bhilai": "Chhattisgarh",
    "Gurgaon": "Haryana",
    "Gurugram": "Haryana",
    "Faridabad": "Haryana",
    "Rohtak": "Haryana",
    "Ambala": "Haryana",
    "Patiala": "Punjab",
    "Bathinda": "Punjab",
    "Jammu": "Jammu & Kashmir",
    "Dibrugarh": "Assam",
    "Silchar": "Assam",
    "Bokaro": "Jharkhand",
    "Dhanbad": "Jharkhand",
    "Muzaffarpur": "Bihar",
    "Bhagalpur": "Bihar",
    "Gaya": "Bihar",
    "Gorakhpur": "Uttar Pradesh",
    "Agra": "Uttar Pradesh",
    "Noida": "Uttar Pradesh",
    "Mathura": "Uttar Pradesh",
    "Vrindavan": "Uttar Pradesh",
    "Rishikesh": "Uttarakhand",
    "Roorkee": "Uttarakhand",
    "Mussouri": "Uttarakhand",
    "Mussoorie": "Uttarakhand",
    "Nainital": "Uttarakhand",
    "Manali": "Himachal Pradesh",
    "Kullu": "Himachal Pradesh",
    "Kasauli": "Himachal Pradesh",
    "Ooty": "Tamil Nadu",
    "Kodaikanal": "Tamil Nadu",
    "Yercaud": "Tamil Nadu",
    "Munnar": "Kerala",
    "Thekkady": "Kerala",
    "Goa": "Goa",
    "Margao": "Goa",
    "Vasco da Gama": "Goa",
    "Jaisalmer": "Rajasthan",
    "Mount Abu": "Rajasthan",
    "Pushkar": "Rajasthan",
    "Kota": "Rajasthan",
    "Alwar": "Rajasthan",
    "Khajuraho": "Madhya Pradesh",
    "Orchha": "Madhya Pradesh",
    "Mandu": "Madhya Pradesh",
    "Kanha": "Madhya Pradesh",
    "Amarkantak": "Madhya Pradesh",
    "Pachmarhi": "Madhya Pradesh",
    "Sanchi": "Madhya Pradesh",
    "Mahabalipuram": "Tamil Nadu",
    "Mamallapuram": "Tamil Nadu",
    "Kanchipuram": "Tamil Nadu",
    "Rameswaram": "Tamil Nadu",
    "Thanjavur": "Tamil Nadu",
    "Kumbakonam": "Tamil Nadu",
    "Chidambaram": "Tamil Nadu",
    "Hampi": "Karnataka",
    "Belur": "Karnataka",
    "Halebid": "Karnataka",
    "Badami": "Karnataka",
    "Pattadakal": "Karnataka",
    "Aihole": "Karnataka",
    "Udupi": "Karnataka",
    "Konark": "Odisha",
    "Bodh Gaya": "Bihar",
    "Bodhgaya": "Bihar",
    "Nalanda": "Bihar",
    "Rajgir": "Bihar",
    "Sarnath": "Uttar Pradesh",
    "Kushinagar": "Uttar Pradesh",
    "Lumbini": "Uttar Pradesh",
    "Shirdi": "Maharashtra",
    "Solapur": "Maharashtra",
    "Kolhapur": "Maharashtra",
    "Alibag": "Maharashtra",
    "Lonavala": "Maharashtra",
    "Mahabaleshwar": "Maharashtra",
    "Matheran": "Maharashtra",
    "Ellora": "Maharashtra",
    "Ajanta": "Maharashtra",
    "Dwaraka": "Gujarat",
    "Dwarka": "Gujarat",
    "Somnath": "Gujarat",
    "Junagadh": "Gujarat",
    "Bhavnagar": "Gujarat",
    "Bhuj": "Gujarat",
    "Mandvi": "Gujarat",
    "Rann of Kutch": "Gujarat",
    # Additional cities
    "Bareilly": "Uttar Pradesh",
    "Amravati": "Maharashtra",
    "Belgaum": "Karnataka",
    "Belagavi": "Karnataka",
    "Jamnagar": "Gujarat",
    "Ahilyanagar": "Maharashtra",
    "Ahmednagar": "Maharashtra",
    "Kanniyakumari": "Tamil Nadu",
    "Kanyakumari": "Tamil Nadu",
    "Saharanpur": "Uttar Pradesh",
    "Moradabad": "Uttar Pradesh",
    "Akola": "Maharashtra",
    "Old Goa": "Goa",
    "Cherrapunji": "Meghalaya",
    "Darbhanga": "Bihar",
    "Panipat": "Haryana",
    "Vijayapura": "Karnataka",
    "Bijapur": "Karnataka",
    "Kakinada": "Andhra Pradesh",
    "Porbandar": "Gujarat",
    "Machilipatnam": "Andhra Pradesh",
    "Ulhasnagar": "Maharashtra",
    "Pathankot": "Punjab",
    "Eluru": "Andhra Pradesh",
    "Hastinapur": "Uttar Pradesh",
    "Bidar": "Karnataka",
    "Burhanpur": "Madhya Pradesh",
    "Thoothukudi": "Tamil Nadu",
    "Tuticorin": "Tamil Nadu",
    "Ballary": "Karnataka",
    "Ballari": "Karnataka",
    "Bellary": "Karnataka",
    "Faizabad": "Uttar Pradesh",
    "Hisar": "Haryana",
    "Jalgaon": "Maharashtra",
    "Ratlam": "Madhya Pradesh",
    "Bharuch": "Gujarat",
    "Munger": "Bihar",
    "Lothal": "Gujarat",
    "Kadapa": "Andhra Pradesh",
    "Cuddapah": "Andhra Pradesh",
    "Bhiwandi": "Maharashtra",
    "Dindigul": "Tamil Nadu",
    "Vidisha": "Madhya Pradesh",
    "Kargil": "Ladakh",
}

for b in data['results']['bindings']:
    name = b.get('itemLabel', {}).get('value', '')
    if name.startswith('Q') or name in seen: continue
    seen.add(name)
    lat = float(b['lat']['value'])
    lon = float(b['lon']['value'])
    image = b.get('image', {}).get('value')
    state = b.get('stateLabel', {}).get('value', '')
    
    # Use fallback map if state is empty or still "Unknown State"
    if not state or state == 'Unknown State' or state.startswith('Q'):
        state = CITY_STATE_MAP.get(name, 'India')
    
    if not image:
        seed = hashlib.md5(name.encode()).hexdigest()[:8]
        image = f"https://picsum.photos/seed/{seed}/480/320"
    
    spots.append({
        'name': name,
        'state': state,
        'country': 'India',
        'lat': lat,
        'lon': lon,
        'image': image,
        'type': 'City',
        'popularity': int(b.get('sitelinks', {}).get('value', 0))
    })

with open('backend/india_spots.json', 'w', encoding='utf-8') as f:
    json.dump(spots, f, ensure_ascii=False, indent=2)

print(f"Saved {len(spots)} spots.")
