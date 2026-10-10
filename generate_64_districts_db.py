import json

# Bangladesh 64 Districts with representative coordinates & Mouzas
districts_data = [
    # Dhaka Division
    {"district": "Dhaka", "mouza": "Mirpur", "lat": 23.8103, "lon": 90.4125},
    {"district": "Gazipur", "mouza": "Tongi", "lat": 23.9888, "lon": 90.3880},
    {"district": "Narayanganj", "mouza": "Siddhirganj", "lat": 23.6238, "lon": 90.5000},
    {"district": "Tangail", "mouza": "Sadar", "lat": 24.2513, "lon": 89.9167},
    {"district": "Faridpur", "mouza": "Goalchamat", "lat": 23.6070, "lon": 89.8406},
    {"district": "Manikganj", "mouza": "Singair", "lat": 23.8617, "lon": 90.0003},
    {"district": "Munshiganj", "mouza": "Garia", "lat": 23.5422, "lon": 90.5305},
    {"district": "Narsingdi", "mouza": "Panchdona", "lat": 23.9193, "lon": 90.7201},
    {"district": "Rajbari", "mouza": "Pangsha", "lat": 23.7574, "lon": 89.6444},
    {"district": "Gopalganj", "mouza": "Tungipara", "lat": 22.9833, "lon": 89.8167},
    {"district": "Madaripur", "mouza": "Rajoir", "lat": 23.1641, "lon": 90.1896},
    {"district": "Shariatpur", "mouza": "Naria", "lat": 23.2423, "lon": 90.4348},
    {"district": "Kishoreganj", "mouza": "Bhairab", "lat": 24.1804, "lon": 90.9812},

    # Chittagong Division
    {"district": "Chattogram", "mouza": "Agrabad", "lat": 22.3244, "lon": 91.8130},
    {"district": "Cox's Bazar", "mouza": "Ramua", "lat": 21.4272, "lon": 92.0058},
    {"district": "Cumilla", "mouza": "Kandirpar", "lat": 23.4607, "lon": 91.1809},
    {"district": "Feni", "mouza": "Dagonbhuiyan", "lat": 23.0159, "lon": 91.3976},
    {"district": "Noakhali", "mouza": "Maijdee", "lat": 22.8696, "lon": 91.0995},
    {"district": "Lakshmipur", "mouza": "Raipur", "lat": 22.9447, "lon": 90.8282},
    {"district": "Brahmanbaria", "mouza": "Ashuganj", "lat": 24.0337, "lon": 91.0086},
    {"district": "Chandpur", "mouza": "Hajiganj", "lat": 23.2321, "lon": 90.6631},
    {"district": "Khagrachhari", "mouza": "Dighinala", "lat": 23.1192, "lon": 91.9847},
    {"district": "Rangamati", "mouza": "Kaptai", "lat": 22.5011, "lon": 92.2184},
    {"district": "Bandarban", "mouza": "Thanchi", "lat": 21.8311, "lon": 92.3686},

    # Rajshahi Division
    {"district": "Rajshahi", "mouza": "Boalia", "lat": 24.3745, "lon": 88.6042},
    {"district": "Bogra", "mouza": "Sherpur", "lat": 24.6700, "lon": 89.3900},
    {"district": "Pabna", "mouza": "Ishwardi", "lat": 24.1531, "lon": 89.0719},
    {"district": "Sirajganj", "mouza": "Ullapara", "lat": 24.3190, "lon": 89.5684},
    {"district": "Naogaon", "mouza": "Dhamoirhat", "lat": 25.0019, "lon": 88.8582},
    {"district": "Natore", "mouza": "Baraigram", "lat": 24.3039, "lon": 89.1706},
    {"district": "Chapai Nawabganj", "mouza": "Shibganj", "lat": 24.6853, "lon": 88.1632},
    {"district": "Joypurhat", "mouza": "Akkelpur", "lat": 25.0315, "lon": 89.0227},

    # Khulna Division
    {"district": "Khulna", "mouza": "Khalishpur", "lat": 22.8456, "lon": 89.5403},
    {"district": "Jashore", "mouza": "Jhikargachha", "lat": 23.1023, "lon": 89.1306},
    {"district": "Kushtia", "mouza": "Bheramara", "lat": 24.0194, "lon": 88.9926},
    {"district": "Satkhira", "mouza": "Kalaroa", "lat": 22.8762, "lon": 89.0412},
    {"district": "Bagerhat", "mouza": "Mongla", "lat": 22.4831, "lon": 89.6056},
    {"district": "Jhenaidah", "mouza": "Kaliganj", "lat": 23.4089, "lon": 89.1384},
    {"district": "Chuadanga", "mouza": "Damurhuda", "lat": 23.6186, "lon": 88.8413},
    {"district": "Meherpur", "mouza": "Gangni", "lat": 23.8344, "lon": 88.6756},
    {"district": "Narail", "mouza": "Lohagara", "lat": 23.1783, "lon": 89.6469},
    {"district": "Magura", "mouza": "Shripur", "lat": 23.6022, "lon": 89.4328},

    # Barisal Division
    {"district": "Barishal", "mouza": "Agailjhara", "lat": 22.7010, "lon": 90.3535},
    {"district": "Bhola", "mouza": "Char Fasson", "lat": 22.1856, "lon": 90.7132},
    {"district": "Patuakhali", "mouza": "Kuakata", "lat": 21.8211, "lon": 90.1223},
    {"district": "Pirojpur", "mouza": "Bhandaria", "lat": 22.4883, "lon": 89.9989},
    {"district": "Barguna", "mouza": "Amtali", "lat": 22.1281, "lon": 90.2289},
    {"district": "Jhalokati", "mouza": "Nalchity", "lat": 22.6181, "lon": 90.2747},

    # Sylhet Division
    {"district": "Sylhet", "mouza": "Zindabazar", "lat": 24.8949, "lon": 91.8687},
    {"district": "Moulvibazar", "mouza": "Sreemangal", "lat": 24.3065, "lon": 91.7296},
    {"district": "Habiganj", "mouza": "Madhabpur", "lat": 24.0983, "lon": 91.2964},
    {"district": "Sunamganj", "mouza": "Tahirpur", "lat": 25.0933, "lon": 91.1764},

    # Rangpur Division
    {"district": "Rangpur", "mouza": "Pirganj", "lat": 25.7439, "lon": 89.2752},
    {"district": "Nilphamari", "mouza": "Chilahati", "lat": 26.1000, "lon": 88.8800},
    {"district": "Dinajpur", "mouza": "Birganj", "lat": 25.8583, "lon": 88.6608},
    {"district": "Gaibandha", "mouza": "Gobindaganj", "lat": 25.1333, "lon": 89.3833},
    {"district": "Kurigram", "mouza": "Nageswari", "lat": 25.9667, "lon": 89.6500},
    {"district": "Lalmonirhat", "mouza": "Patgram", "lat": 26.3500, "lon": 89.0167},
    {"district": "Panchagarh", "mouza": "Tetulia", "lat": 26.5833, "lon": 88.3500},
    {"district": "Thakurgaon", "mouza": "Pirganj", "lat": 25.8500, "lon": 88.3667},

    # Mymensingh Division
    {"district": "Mymensingh", "mouza": "Muktagachha", "lat": 24.7571, "lon": 90.2625},
    {"district": "Jamalpur", "mouza": "Sarbari", "lat": 24.9197, "lon": 89.9481},
    {"district": "Netrokona", "mouza": "Durgapur", "lat": 25.1264, "lon": 90.5872},
    {"district": "Sherpur", "mouza": "Nalitabari", "lat": 25.1833, "lon": 90.1833}
]

owners = [
    ("Abdul Karim", "আব্দুল করিম"),
    ("Rahima Begum", "রহিমা বেগম"),
    ("Kamal Hossain", "কামাল হোসেন"),
    ("Ekramul Haq", "একরামুল হক"),
    ("Absar Ali", "আবছার আলী"),
    ("Mahatab Uddin", "মাহাতাব উদ্দিন"),
    ("Sultan Mahmud", "সুলতান মাহমুদ"),
    ("Nazmul Islam", "নাজমুল ইসলাম")
]

features = []
plot_counter = 101

for idx, item in enumerate(districts_data):
    for p_offset in range(2): # Protita zilai 2-ti kore Plot (Total 128 plots)
        plot_no = str(plot_counter)
        khatian_no = str(2000 + plot_counter)
        owner_en, owner_bn = owners[(idx + p_offset) % len(owners)]
        
        base_lat = item["lat"] + (p_offset * 0.001)
        base_lon = item["lon"] + (p_offset * 0.001)
        
        polygon_coords = [
            [base_lon, base_lat],
            [base_lon + 0.002, base_lat],
            [base_lon + 0.002, base_lat + 0.002],
            [base_lon, base_lat + 0.002],
            [base_lon, base_lat]
        ]
        
        feature = {
            "type": "Feature",
            "properties": {
                "plot_no": plot_no,
                "khatian_no": khatian_no,
                "owner_name": owner_en,
                "owner_name_bn": owner_bn,
                "mouza": item["mouza"],
                "jl_no": str((idx % 90) + 1),
                "khatian_type": "RS",
                "land_type": "নাল / ভিটি",
                "district": item["district"],
                "declared_area": f"0.{10 + (p_offset * 5)} Acre"
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [polygon_coords]
            }
        }
        features.append(feature)
        plot_counter += 1

# Special addition for handwritten test cases (3365, 3364, 501, 502)
special_plots = [
    {"plot_no": "3365", "khatian_no": "4232", "district": "Nilphamari", "mouza": "Chilahati", "lat": 26.1000, "lon": 88.8800},
    {"plot_no": "3364", "khatian_no": "4232", "district": "Nilphamari", "mouza": "Chilahati", "lat": 26.1010, "lon": 88.8810},
    {"plot_no": "501", "khatian_no": "1203", "district": "Dhaka", "mouza": "Mirpur", "lat": 23.8103, "lon": 90.4125},
    {"plot_no": "502", "khatian_no": "1204", "district": "Dhaka", "mouza": "Mirpur", "lat": 23.8115, "lon": 90.4135}
]

for sp in special_plots:
    polygon_coords = [
        [sp["lon"], sp["lat"]],
        [sp["lon"] + 0.002, sp["lat"]],
        [sp["lon"] + 0.002, sp["lat"] + 0.002],
        [sp["lon"], sp["lat"] + 0.002],
        [sp["lon"], sp["lat"]]
    ]
    features.append({
        "type": "Feature",
        "properties": {
            "plot_no": sp["plot_no"],
            "khatian_no": sp["khatian_no"],
            "owner_name": "Ekramul Haq & Absar Ali",
            "owner_name_bn": "একরামুল হক ও আবছার আলী",
            "mouza": sp["mouza"],
            "jl_no": "51",
            "khatian_type": "RS",
            "land_type": "সয়লা / ডোবা",
            "district": sp["district"],
            "declared_area": "0.21 Acre"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [polygon_coords]
        }
    })

geojson_data = {
    "type": "FeatureCollection",
    "features": features
}

with open("sample_data.geojson", "w", encoding="utf-8") as f:
    json.dump(geojson_data, f, ensure_ascii=False, indent=2)

print(f"Successfully generated {len(features)} plots covering ALL 64 Districts of Bangladesh in sample_data.geojson!")