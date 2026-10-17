import argparse
import json
import math
import os
from pathlib import Path

LOCATION_INDEX_PATH = Path(__file__).resolve().with_name("bangladesh_adm3_locations.json")
GIVEN_NAMES = [
    ("Abdul Karim", "আব্দুল করিম"),
    ("Abdul Jalil", "আব্দুল জলিল"),
    ("Abdul Malek", "আব্দুল মালেক"),
    ("Abdul Hannan", "আব্দুল হান্নান"),
    ("Abdul Quddus", "আব্দুল কুদ্দুস"),
    ("Abdul Baten", "আব্দুল বাতেন"),
    ("Abdul Matin", "আব্দুল মতিন"),
    ("Abdullah", "আব্দুল্লাহ"),
    ("Abul Kalam", "আবুল কালাম"),
    ("Amina", "আমিনা"),
    ("Anwara", "আনোয়ারা"),
    ("Asma", "আসমা"),
    ("Aysha", "আয়েশা"),
    ("Babul", "বাবুল"),
    ("Belal", "বেলাল"),
    ("Bilkis", "বিলকিস"),
    ("Biplob", "বিপ্লব"),
    ("Delwar", "দেলোয়ার"),
    ("Farida", "ফরিদা"),
    ("Faruk", "ফারুক"),
    ("Ferdousi", "ফেরদৌসী"),
    ("Habibullah", "হাবিবুল্লাহ"),
    ("Hafizur", "হাফিজুর"),
    ("Hamida", "হামিদা"),
    ("Hasina", "হাসিনা"),
    ("Helal", "হেলাল"),
    ("Ibrahim", "ইব্রাহিম"),
    ("Jamal", "জামাল"),
    ("Jannatul", "জান্নাতুল"),
    ("Jasim", "জসিম"),
    ("Joya", "জয়া"),
    ("Kawsar", "কাওসার"),
    ("Khadija", "খাদিজা"),
    ("Khaleda", "খালেদা"),
    ("Laila", "লায়লা"),
    ("Mahbub", "মাহবুব"),
    ("Mahfuza", "মাহফুজা"),
    ("Mizanur", "মিজানুর"),
    ("Monir", "মনির"),
    ("Nasima", "নাসিমা"),
    ("Nurul", "নুরুল"),
    ("Osman", "ওসমান"),
    ("Parvin", "পারভীন"),
    ("Rahima", "রহিমা"),
    ("Rehana", "রেহানা"),
    ("Rokeya", "রোকেয়া"),
    ("Rubina", "রুবিনা"),
    ("Salma", "সালমা"),
    ("Shafiqul", "শফিকুল"),
    ("Shahana", "শাহানা"),
    ("Shamsul", "শামসুল"),
    ("Shirin", "শিরিন"),
    ("Sirajul", "সিরাজুল"),
    ("Sohel", "সোহেল"),
    ("Tahmina", "তাহমিনা"),
    ("Taslima", "তাসলিমা"),
    ("Zahir", "জাহির"),
    ("Zohra", "জোহরা"),
    ("Tanjila", "তানজিলা"),
    ("Rafiq", "রফিক"),
    ("Mostafa", "মোস্তফা"),
    ("Enamul", "এনামুল"),
    ("Lutfur", "লুৎফর"),
    ("Saiful", "সাইফুল"),
    ("Shamsun", "শামসুন"),
    ("Nazma", "নাজমা"),
    ("Nur Jahan", "নুরজাহান"),
    ("Anwar", "আনোয়ার"),
    ("Rashed", "রাশেদ"),
    ("Julekha", "জুলেখা"),
    ("Sajeda", "সাজেদা"),
    ("Rafiqul", "রফিকুল"),
    ("Shahidul", "শহিদুল"),
    ("Anisur", "আনিসুর"),
    ("Asaduzzaman", "আসাদুজ্জামান"),
    ("Mannan", "মান্নান"),
    ("Jahangir", "জাহাঙ্গীর"),
    ("Shah Alam", "শাহ আলম"),
]

FAMILY_NAMES = [
    ("Ahmed", "আহমেদ"),
    ("Akter", "আক্তার"),
    ("Alam", "আলম"),
    ("Ali", "আলী"),
    ("Anwar", "আনোয়ার"),
    ("Banu", "বানু"),
    ("Begum", "বেগম"),
    ("Bhuiyan", "ভূঁইয়া"),
    ("Biswas", "বিশ্বাস"),
    ("Chowdhury", "চৌধুরী"),
    ("Das", "দাস"),
    ("Dewan", "দেওয়ান"),
    ("Gazi", "গাজী"),
    ("Haque", "হক"),
    ("Hossain", "হোসেন"),
    ("Islam", "ইসলাম"),
    ("Jahan", "জাহান"),
    ("Khatun", "খাতুন"),
    ("Khan", "খান"),
    ("Mahmud", "মাহমুদ"),
    ("Mia", "মিয়া"),
    ("Mollah", "মোল্লা"),
    ("Mondal", "মণ্ডল"),
    ("Nahar", "নাহার"),
    ("Paul", "পাল"),
    ("Rahman", "রহমান"),
    ("Roy", "রায়"),
    ("Saha", "সাহা"),
    ("Sarker", "সরকার"),
    ("Sardar", "সরদার"),
    ("Sheikh", "শেখ"),
    ("Sikder", "সিকদার"),
    ("Talukder", "তালুকদার"),
    ("Uddin", "উদ্দিন"),
    ("Yasmin", "ইয়াসমিন"),
    ("Bari", "বারী"),
    ("Bashar", "বাশার"),
    ("Chandra", "চন্দ্র"),
    ("Datta", "দত্ত"),
    ("Fakir", "ফকির"),
    ("Farazi", "ফরাজী"),
    ("Haldar", "হালদার"),
    ("Howlader", "হাওলাদার"),
    ("Kabir", "কবির"),
    ("Karmakar", "কর্মকার"),
    ("Majumder", "মজুমদার"),
    ("Malik", "মালিক"),
    ("Mandal", "মণ্ডল"),
    ("Matin", "মতিন"),
    ("Mitra", "মিত্র"),
    ("Nath", "নাথ"),
    ("Pal", "পাল"),
    ("Patowary", "পাটোয়ারী"),
    ("Pramanik", "প্রামাণিক"),
    ("Rana", "রানা"),
    ("Rashid", "রশীদ"),
    ("Saha", "সাহা"),
    ("Sanyal", "সান্যাল"),
    ("Sarkar", "সরকার"),
    ("Sen", "সেন"),
    ("Shah", "শাহ"),
    ("Shikdar", "শিকদার"),
    ("Sutradhar", "সূত্রধর"),
    ("Tarafdar", "তরফদার"),
    ("Thakur", "ঠাকুর"),
    ("Zaman", "জামান"),
    ("Amin", "আমিন"),
    ("Barman", "বর্মন"),
    ("Basu", "বসু"),
    ("Biswas", "বিশ্বাস"),
    ("Ghosh", "ঘোষ"),
    ("Guha", "গুহ"),
    ("Hawlader", "হাওলাদার"),
    ("Karim", "করিম"),
    ("Mollah", "মোল্লা"),
    ("Nandi", "নন্দী"),
    ("Poddar", "পোদ্দার"),
    ("Siddique", "সিদ্দিক"),
    ("Sikdar", "সিকদার"),
    ("Uddin", "উদ্দিন"),
    ("Aich", "আইচ"),
    ("Barua", "বড়ুয়া"),
    ("Mahato", "মাহাতো"),
    ("Baidya", "বৈদ্য"),
]

def rectangle(longitude, latitude, width, height):
    return [
        [
            [longitude, latitude],
            [longitude + width, latitude],
            [longitude + width, latitude + height],
            [longitude, latitude + height],
            [longitude, latitude],
        ]
    ]


def area_square_metres(latitude, width_degrees, height_degrees):
    metres_per_degree_latitude = 111_132
    metres_per_degree_longitude = 111_320 * math.cos(math.radians(latitude))
    return round(
        width_degrees
        * metres_per_degree_longitude
        * height_degrees
        * metres_per_degree_latitude,
        2,
    )


def load_administrative_locations(location_index_path=LOCATION_INDEX_PATH):
    location_data = json.loads(
        location_index_path.read_text(encoding="utf-8")
    )
    locations = location_data["locations"]
    expected_count = location_data["metadata"]["unit_count"]
    if len(locations) != expected_count:
        raise ValueError(
            f"Location index declares {expected_count} units but contains {len(locations)}."
        )
    if len({location["admin_unit_id"] for location in locations}) != len(locations):
        raise ValueError("Location index contains duplicate administrative unit IDs.")
    return location_data


def owner_name_for_index(index):
    family_names = []
    seen_bengali_names = set()
    for english_name, bengali_name in FAMILY_NAMES:
        if bengali_name not in seen_bengali_names:
            family_names.append((english_name, bengali_name))
            seen_bengali_names.add(bengali_name)
    names_per_cycle = len(GIVEN_NAMES) * len(family_names)
    cycle, name_index = divmod(index, names_per_cycle)
    given_index, family_index = divmod(name_index, len(family_names))
    given_en, given_bn = GIVEN_NAMES[given_index]
    family_en, family_bn = family_names[family_index]
    suffix_en = f" {cycle + 1}" if cycle else ""
    suffix_bn = f" {cycle + 1}" if cycle else ""
    return (
        f"{given_en} {family_en}{suffix_en}",
        f"{given_bn} {family_bn}{suffix_bn}",
    )


def generate_demo_data(
    plots_per_upazila,
    roads_per_upazila,
    location_index_path=LOCATION_INDEX_PATH,
):
    location_data = load_administrative_locations(location_index_path)
    locations = location_data["locations"]
    features = []
    plot_number = 1
    khatian_number = 1
    owner_number = 0
    cell_width = 0.00018
    cell_height = 0.00018
    cell_step = 0.00024
    road_width = 0.000025
    acres_per_square_metre = 1 / 4046.8564224
    district_counts = {}
    upazila_counts = {}

    for location in locations:
        columns = min(10, max(1, math.ceil(math.sqrt(plots_per_upazila))))
        rows = math.ceil(plots_per_upazila / columns)
        unit_land_count = 0
        unit_road_count = 0
        mouza = f"DEMO-{location['district']}-{location['upazila']}"
        mouza_bn = (
            f"ডেমো মৌজা ({location['district']} - {location['upazila']})"
        )

        for offset in range(plots_per_upazila):
            row, column = divmod(offset, columns)
            longitude = location["longitude"] + column * cell_step
            latitude = location["latitude"] + row * cell_step
            area_sqm = area_square_metres(latitude, cell_width, cell_height)
            owner_en, owner_bn = owner_name_for_index(owner_number)
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "plot_no": str(plot_number),
                        "khatian_no": str(khatian_number),
                        "owner_name": owner_en,
                        "owner_name_bn": owner_bn,
                        "mouza": mouza,
                        "mouza_bn": mouza_bn,
                        "upazila": location["upazila"],
                        "admin_unit_id": location["admin_unit_id"],
                        "district": location["district"],
                        "khatian_type": "DEMO",
                        "land_type": "ডেমো আবাদি জমি",
                        "declared_area": f"{area_sqm * acres_per_square_metre:.4f} Acre",
                        "area_sqm": area_sqm,
                        "record_type": "synthetic_land_plot",
                        "is_demo": True,
                        "data_source": (
                            "Synthetic demo record; location is an ADM3 representative "
                            "point, not a cadastral, mouza, or ownership record."
                        ),
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": rectangle(
                            longitude,
                            latitude,
                            cell_width,
                            cell_height,
                        ),
                    },
                }
            )
            plot_number += 1
            khatian_number += 1
            owner_number += 1
            unit_land_count += 1

        for road_offset in range(roads_per_upazila):
            gap_index = min(
                rows - 1,
                max(0, round((road_offset + 1) * rows / (roads_per_upazila + 1)) - 1),
            )
            latitude = location["latitude"] + gap_index * cell_step + cell_height + (
                cell_step - cell_height - road_width
            ) / 2
            longitude = location["longitude"]
            road_length = (columns - 1) * cell_step + cell_width
            area_sqm = area_square_metres(latitude, road_length, road_width)
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "plot_no": str(plot_number),
                        "khatian_no": str(khatian_number),
                        "owner_name": "Government (demo)",
                        "owner_name_bn": "সরকার (ডেমো)",
                        "mouza": mouza,
                        "mouza_bn": mouza_bn,
                        "upazila": location["upazila"],
                        "admin_unit_id": location["admin_unit_id"],
                        "district": location["district"],
                        "khatian_type": "DEMO",
                        "land_type": "সরকারি রাস্তা (ডেমো)",
                        "declared_area": f"{area_sqm * acres_per_square_metre:.4f} Acre",
                        "area_sqm": area_sqm,
                        "record_type": "synthetic_government_road",
                        "is_demo": True,
                        "data_source": (
                            "Synthetic demo road; not an official road or cadastral boundary."
                        ),
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": rectangle(
                            longitude,
                            latitude,
                            road_length,
                            road_width,
                        ),
                    },
                }
            )
            plot_number += 1
            khatian_number += 1
            unit_road_count += 1

        district_count = district_counts.setdefault(
            location["district"],
            {"synthetic_land_plots": 0, "synthetic_government_roads": 0},
        )
        district_count["synthetic_land_plots"] += unit_land_count
        district_count["synthetic_government_roads"] += unit_road_count
        upazila_counts[location["admin_unit_id"]] = {
            "district": location["district"],
            "upazila": location["upazila"],
            "synthetic_land_plots": unit_land_count,
            "synthetic_government_roads": unit_road_count,
        }

    return {
        "type": "FeatureCollection",
        "metadata": {
            "title": "Bangladesh ADM3 synthetic demo dataset",
            "is_demo": True,
            "authoritative": False,
            "coverage_note": (
                "Synthetic sample features are generated for all 544 ADM3 units "
                "in the bundled 2020 geoBoundaries source, covering all 64 districts. "
                "ADM3 includes subdistrict and metropolitan thana units. Coordinates "
                "are representative points, not parcel locations. Mouza labels and "
                "land/road records are synthetic; this is not a complete or official "
                "mouza, cadastral, ownership, or road database."
            ),
            "administrative_unit_count": len(locations),
            "district_count": len(district_counts),
            "synthetic_land_plot_count": len(locations) * plots_per_upazila,
            "synthetic_government_road_count": len(locations) * roads_per_upazila,
            "feature_count": len(features),
            "administrative_boundary_source": location_data["metadata"]["source"],
            "administrative_boundary_attribution": location_data["metadata"],
            "synthetic_mouza_labels": True,
            "numeric_only_plot_and_khatian_numbers": True,
            "unique_synthetic_landowner_names": True,
            "counts_by_district": district_counts,
            "counts_by_upazila": upazila_counts,
        },
        "features": features,
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate synthetic demo polygons across Bangladesh's 2020 ADM3 "
            "subdistrict and metropolitan thana units."
        )
    )
    parser.add_argument(
        "--plots-per-upazila",
        type=int,
        default=10,
        help="Synthetic land plots to generate per ADM3 unit (default: 10).",
    )
    parser.add_argument(
        "--roads-per-upazila",
        type=int,
        default=2,
        help="Synthetic road parcels to generate per ADM3 unit (default: 2).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().with_name("bangladesh_demo_data.geojson"),
        help="Output GeoJSON path (default: bangladesh_demo_data.geojson).",
    )
    args = parser.parse_args()

    if args.plots_per_upazila < 1:
        parser.error("--plots-per-upazila must be at least 1.")
    if args.roads_per_upazila < 0:
        parser.error("--roads-per-upazila cannot be negative.")

    output_path = args.output.resolve()
    protected_sample = Path(__file__).resolve().with_name("sample_data.geojson")
    if output_path == protected_sample:
        parser.error("Refusing to overwrite sample_data.geojson; choose a separate demo output.")

    geojson_data = generate_demo_data(
        args.plots_per_upazila,
        args.roads_per_upazila,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f"{output_path.name}.tmp")
    temporary_path.write_text(
        json.dumps(geojson_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary_path, output_path)

    metadata = geojson_data["metadata"]
    print(
        f"Generated {metadata['feature_count']} synthetic demo records "
        f"({metadata['synthetic_land_plot_count']} land plots + "
        f"{metadata['synthetic_government_road_count']} road parcels) "
        f"across {metadata['administrative_unit_count']} administrative units "
        f"in {metadata['district_count']} districts: {output_path}"
    )
    print(metadata["coverage_note"])


if __name__ == "__main__":
    main()