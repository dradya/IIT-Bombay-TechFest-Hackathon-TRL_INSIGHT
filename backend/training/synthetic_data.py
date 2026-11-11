"""Synthetic DEMONSTRATION dataset generator.

IMPORTANT: this generator exists ONLY for local functional testing and
for demonstrating the training pipeline when no official labelled data
is available. Every generated row is tagged ``source = SYNTHETIC_DEMO``
and every derived artefact reports ``dataset_type = synthetic_demo`` so
that demonstration results can never be mistaken for real-world or
competition benchmark results.

The documents are constructed so that:
  * low-TRL documents describe principles/concepts/POC as completed work
    and mention higher-level activities only as PLANNED/FUTURE work;
  * high-TRL documents contain completed, results-bearing statements for
    their band plus realistic lower-band background;
  * every document contains distractors (limitations, future work,
    background) so that trivial keyword matching is insufficient.
"""
from __future__ import annotations

import random
from typing import Any

DOMAINS: list[dict[str, Any]] = [
    {
        "name": "Water Treatment",
        "tech": [
            "membrane distillation unit", "solar desalination module",
            "electrocoagulation reactor", "biological filter column",
        ],
        "components": ["hydrophobic membrane cassette", "pump and controller",
                       "flat-sheet module", "aeration header"],
        "phenomena": ["vapour pressure gradient", "zeta potential shift",
                      "biofilm attachment", "ionic rejection"],
        "metrics": [("permeate flux", "L/m2h"), ("salt rejection", "%"),
                    ("COD removal", "%"), ("turbidity removal", "%")],
        "values": ["18.4", "99.7", "92.1", "4.6"],
        "standards": ["ISO 24512", "WHO drinking-water guidelines"],
        "sites": ["roof test bay", "pilot plant yard", "remote village site"],
        "applications": ["off-grid brackish water treatment",
                         "municipal pre-treatment", "industrial effluent recycling"],
    },
    {
        "name": "Renewable Energy",
        "tech": ["perovskite solar cell stack", "micro-wind turbine",
                 "green hydrogen electrolyser", "battery thermal management unit"],
        "components": ["charge controller", "enclosure and mast",
                       "MEA assembly", "cooling plate"],
        "phenomena": ["photovoltaic conversion", "aerodynamic lift",
                      "electrolysis overpotential", "lithium plating"],
        "metrics": [("conversion efficiency", "%"), ("capacity factor", "%"),
                    ("hydrogen yield", "Nm3/h"), ("cycle retention", "%")],
        "values": ["21.3", "31.7", "1.85", "94.2"],
        "standards": ["IEC 61215", "IEC 62282", "UL 1973"],
        "sites": ["rooftop array", "coastal test field", "pilot electrolysis skid"],
        "applications": ["rural electrification", "peak-shaving storage",
                         "industrial hydrogen supply"],
    },
    {
        "name": "Healthcare Devices",
        "tech": ["portable spirometer", "wearable ECG patch",
                 "rapid diagnostic cassette", "infusion control module"],
        "components": ["flow sensor board", "electrode array",
                       "microfluidic channel", "dosage actuator"],
        "phenomena": ["turbulent airflow resistance", "bio-impedance change",
                      "capillary wicking", "pressure occlusion"],
        "metrics": [("measurement accuracy", "%"), ("sensitivity", "%"),
                    ("specificity", "%"), ("dose error", "%")],
        "values": ["96.5", "94.1", "97.8", "2.3"],
        "standards": ["ISO 13485", "IEC 60601-1", "ISO 10993"],
        "sites": ["hospital ward", "clinic trial room", "field health post"],
        "applications": ["point-of-care screening", "home monitoring",
                         "emergency triage"],
    },
    {
        "name": "Agriculture",
        "tech": ["drip irrigation controller", "soil moisture sensor node",
                 "drone spray platform", "grain storage monitor"],
        "components": ["solenoid valve bank", "capacitive probe",
                       "spray boom", "humidity logger"],
        "phenomena": ["soil water potential", "canopy droplet adhesion",
                      "respiratory heat build-up", "dielectric permittivity"],
        "metrics": [("water saving", "%"), ("yield gain", "%"),
                    ("dose uniformity", "%"), ("spoilage reduction", "%")],
        "values": ["27.4", "12.6", "91.2", "18.9"],
        "standards": ["FAO irrigation guidelines", "ISO 11276"],
        "sites": ["demonstration farm", "open field plot", "storage warehouse"],
        "applications": ["smallholder irrigation", "greenhouse fertigation",
                         "post-harvest storage"],
    },
    {
        "name": "Advanced Materials",
        "tech": ["self-healing coating", "graphene composite panel",
                 "high-entropy alloy liner", "phase-change thermal pad"],
        "components": ["microcapsule dispersion", "filler matrix",
                       "deposition layer", "binder system"],
        "phenomena": ["crack-tip healing", "interfacial load transfer",
                      "solid-solution strengthening", "latent heat exchange"],
        "metrics": [("hardness", "HV"), ("thermal conductivity", "W/mK"),
                    ("tensile strength", "MPa"), ("healing efficiency", "%")],
        "values": ["412", "6.7", "780", "88"],
        "standards": ["ASTM G17", "ISO 28192", "ASTM E8"],
        "sites": ["spray booth", "weathering chamber", "process pilot line"],
        "applications": ["pipeline corrosion protection", "battery casing",
                         "building envelope panels"],
    },
    {
        "name": "Mobility & Transport",
        "tech": ["regenerative braking controller", "lightweight wheel hub",
                 "battery swap cabinet", "collision warning unit"],
        "components": ["inverter stage", "bearing assembly",
                       "contact arm", "radar module"],
        "phenomena": ["back-EMF recovery", "contact resistance",
                      "fatigue crack growth", "doppler shift"],
        "metrics": [("energy recovery", "%"), ("mass reduction", "%"),
                    ("swap time", "s"), ("detection range", "m")],
        "values": ["23.8", "17.5", "4.2", "140"],
        "standards": ["UN ECE R10", "ISO 26262", "SAE J1772"],
        "sites": ["test track", "urban pilot route", "depot yard"],
        "applications": ["last-mile delivery fleets", "transit buses",
                         "shared mobility stations"],
    },
    {
        "name": "Digital & Software",
        "tech": ["edge inference engine", "federated analytics service",
                 "fault-tolerant scheduler", "anomaly detection pipeline"],
        "components": ["model runtime", "message broker",
                       "checkpoint store", "feature store"],
        "phenomena": ["gradient staleness", "tail latency inflation",
                      "partition tolerance", "concept drift"],
        "metrics": [("inference latency", "ms"), ("recall", "%"),
                    ("uptime", "%"), ("throughput", "req/s")],
        "values": ["14.2", "93.4", "99.6", "820"],
        "standards": ["ISO/IEC 27001", "IEEE 730", "SOC 2"],
        "sites": ["staging cluster", "customer tenant", "production region"],
        "applications": ["predictive maintenance", "retail demand forecasting",
                         "network security monitoring"],
    },
    {
        "name": "Aerospace & Sensors",
        "tech": ["hypersonic thermal tile", "satellite star tracker",
                 "drone navigation module", "structural health sensor"],
        "components": ["ceramic substrate", "baffle assembly",
                       "IMU board", "piezo patch"],
        "phenomena": ["radiative heat flux", "star centroid drift",
                      "vibration coupling", "strain wave propagation"],
        "metrics": [("pointing accuracy", "arcsec"), ("mass", "kg"),
                    ("drift rate", "deg/h"), ("damage detection", "%")],
        "values": ["3.1", "0.42", "0.08", "97"],
        "standards": ["ECSS-Q-ST-70", "DO-178C", "MIL-STD-810"],
        "sites": ["thermal vacuum chamber", "avionics bench", "flight test range"],
        "applications": ["low-earth-orbit payloads", "high-altitude platforms",
                         "launch-vehicle structures"],
    },
]

# Completed statements per TRL band. {slots} are filled per document.
BAND_TEMPLATES: dict[int, list[str]] = {
    1: [
        "The underlying scientific principle of {tech} was studied in this work.",
        "A theoretical analysis of {phenomenon} was carried out using first-principles models.",
        "First-principles calculations show that {phenomenon} governs the behaviour of the {tech}.",
        "The observed {phenomenon} is consistent with established theory and was reported in a peer-reviewed publication.",
        "Fundamental investigation of {phenomenon} established the physical basis for the {tech}.",
        "Governing equations describing {phenomenon} were derived and analysed.",
    ],
    2: [
        "We propose a compact {tech} concept for {application}.",
        "The technology concept integrates the {component} with a control unit.",
        "A feasibility study was carried out to identify the intended application of the {tech}.",
        "The design architecture defines how the {component} is arranged within the {tech}.",
        "We hypothesise that {phenomenon} can be exploited to improve {metric} of the {tech}.",
        "An invention disclosure covering the {tech} was filed by {org}.",
        "The concept of operation for the {tech} was formulated and documented.",
    ],
    3: [
        "A proof-of-concept experiment was performed in the laboratory.",
        "Here we demonstrate the feasibility of the {tech} using a bench-top rig.",
        "Results show a {metric} of {value} {unit} in the initial test.",
        "The proof of concept validated the core mechanism of the {tech}.",
        "Experimental verification of the working principle was completed with measured data.",
        "The initial validation experiment confirmed the expected {phenomenon} behaviour.",
    ],
    4: [
        "Laboratory tests were conducted on the integrated {component} set.",
        "The breadboard implementation was characterized on a controlled test bench.",
        "The subsystem was tested in the laboratory for {n} hours of continuous operation.",
        "Measured {metric} in the laboratory reached {value} {unit}.",
        "The integrated components were validated together under controlled laboratory conditions.",
        "Component validation in the lab confirmed the design requirements were met.",
    ],
    5: [
        "The subsystem was validated in a relevant environment using a pilot-scale rig.",
        "Testing under representative conditions confirmed a {metric} of {value} {unit}.",
        "Environmental chamber tests were performed under field-representative conditions.",
        "The pilot-scale system was evaluated in a simulated environment at {site}.",
        "Validation in the relevant environment showed performance close to the laboratory results.",
        "The {tech} was tested under realistic operating conditions at {site}.",
    ],
    6: [
        "The integrated prototype was demonstrated in a relevant environment at {site}.",
        "A full prototype demonstration was carried out over {n} weeks at {site}.",
        "The system-level demonstration addressed all major issues, which were corrected.",
        "Representative field conditions were used for the subsystem demonstration.",
        "The prototype achieved a {metric} of {value} {unit} during the representative demonstration.",
        "The integrated model was demonstrated under representative conditions without critical failures.",
    ],
    7: [
        "The system prototype was demonstrated in the operational environment during a {n}-day field trial at {site}.",
        "On-site trials at the operational site showed stable operation of the {tech}.",
        "The prototype was evaluated by end users in a live operational scenario.",
        "Data from the field trial demonstrate reliable operation of the {tech} in service.",
        "An operational trial was performed with {org} personnel at {site}.",
        "The complete prototype was operated in its intended environment for {n} days.",
    ],
    8: [
        "The complete system passed qualification testing against {standard}.",
        "Acceptance tests were completed and the system was certified by {org}.",
        "Reliability qualification testing confirmed compliance with {standard}.",
        "The final system is production ready after type approval.",
        "Qualification testing of the final-form system was completed with no open corrective actions.",
        "The system was qualified and handed over for series production.",
    ],
    9: [
        "The {tech} has been in commercial operation since {year}.",
        "Full-scale deployment at {site} has been running for {n} months.",
        "The technology is deployed in routine operation with {uptime} uptime.",
        "Operational data from {n} installed units confirm sustained service of the {tech}.",
        "The system has proven itself in daily operation with {org} users.",
        "Commercial deployment of the {tech} continues across multiple customer sites.",
    ],
}

# Distractors - present in documents of every band (they must NOT shift the label).
BACKGROUND = [
    "Water and resource scarcity affects millions of people worldwide and motivates this line of work.",
    "The market for {application} has grown steadily over the past decade.",
    "Prior art in {phenomenon} was reviewed from more than forty peer-reviewed sources.",
    "The team at {org} has worked on {tech} related problems since {year}.",
    "Regulatory expectations for {application} are becoming stricter every year.",
]

LIMITATIONS = [
    "The main limitation of this study is the short duration of the reported tests.",
    "The results were obtained with a single unit and may vary between units.",
    "Cost analysis remains preliminary and requires further data.",
    "The influence of long-term fouling was not assessed in this report.",
]

FUTURE_PLANNED = [
    "Future work will include commercial deployment and certification testing of the {tech}.",
    "The next phase will involve qualification testing to certify the unit.",
    "Full-scale deployment is planned for next year at customer sites.",
    "In future studies the system will be tested in the operational environment.",
    "A certification campaign is scheduled for the coming quarter.",
]

NEGATIVE_NOTES = [
    "The system has not yet been certified for series production.",
    "No commercial deployment has taken place at the time of writing.",
    "The prototype has not been tested in the operational environment.",
]

# Explicit PLANNED (future-tense) versions of the higher bands. These teach
# the model that future intent does not prove completion.
FUTURE_BY_BAND: dict[int, list[str]] = {
    3: ["A proof-of-concept experiment will be performed in the laboratory."],
    4: ["Laboratory tests will be conducted on the integrated {component} set."],
    5: ["The subsystem will be validated in a relevant environment using a pilot rig."],
    6: ["The integrated prototype will be demonstrated in a relevant environment at {site}."],
    7: ["A field trial will be organised in the operational environment at {site}."],
    8: ["Qualification testing will be performed to certify the complete system."],
    9: ["The system will be deployed commercially at customer sites."],
}

ORGANISATIONS = ["BlueRiver Labs", "Northfield Institute", "SunTech Solutions",
                 "Delta Research Centre", "Horizon Materials Group",
                 "Kestrel Engineering", "Meridian Labs"]

SECTION_HEADINGS = [
    "1 Introduction", "2 Background", "3 Concept Design", "4 Experimental Setup",
    "5 Results", "6 Discussion", "7 Field Evaluation", "8 Future Work",
    "9 Conclusion",
]


def _fill(template: str, domain: dict[str, Any], rng: random.Random, org: str, year: int) -> str:
    metric, unit = rng.choice(domain["metrics"])
    return template.format(
        tech=rng.choice(domain["tech"]),
        component=rng.choice(domain["components"]),
        phenomenon=rng.choice(domain["phenomena"]),
        metric=metric,
        unit=unit,
        value=rng.choice(domain["values"]),
        standard=rng.choice(domain["standards"]),
        site=rng.choice(domain["sites"]),
        application=rng.choice(domain["applications"]),
        n=rng.choice([3, 5, 7, 14, 30, 60, 90, 180, 365]),
        org=org,
        year=year,
        uptime=rng.choice(["98.4%", "99.1%", "99.6%"]),
    )


def generate_document(label: int, domain: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    """Build one synthetic document whose dominant completed band == label."""
    org = rng.choice(ORGANISATIONS)
    year = rng.randint(2019, 2025)
    paragraphs: list[str] = []

    # Background (1-2 sentences, any band - pure distractor)
    for _ in range(rng.randint(1, 2)):
        paragraphs.append(_fill(rng.choice(BACKGROUND), domain, rng, org, year))

    # Completed statements for bands <= label (ascending, weighted to label band)
    bands = list(range(1, label + 1))
    for band in bands:
        if band == label:
            count = rng.randint(3, 4)
        elif band >= max(1, label - 2):
            count = rng.randint(1, 2)
        else:
            count = 1 if rng.random() < 0.5 else 0
        templates = BAND_TEMPLATES[band]
        chosen = rng.sample(templates, min(count, len(templates)))
        for template in chosen:
            paragraphs.append(_fill(template, domain, rng, org, year))

    # Higher-band activities: only as PLANNED or NEGATED for labels < 9
    if label < 9:
        higher_bands = [b for b in range(label + 1, 10)]
        mention = sorted(
            rng.sample(higher_bands, k=min(len(higher_bands), rng.randint(1, 2)))
        )
        if rng.random() < 0.65:
            paragraphs.append(_fill(rng.choice(FUTURE_PLANNED), domain, rng, org, year))
        if rng.random() < 0.45:
            paragraphs.append(_fill(rng.choice(NEGATIVE_NOTES), domain, rng, org, year))
        # Band-specific planned statements for the next higher bands
        for band in mention[:2]:
            options = FUTURE_BY_BAND.get(band, [])
            if options:
                paragraphs.append(_fill(rng.choice(options), domain, rng, org, year))

    # Limitation + occasional future-work heading paragraph
    paragraphs.append(_fill(rng.choice(LIMITATIONS), domain, rng, org, year))

    # Assemble with headings for a realistic report structure
    rng.shuffle(paragraphs)
    parts: list[str] = [
        f"{domain['name'].upper()}: TECHNICAL REPORT ON "
        f"{rng.choice(domain['tech']).upper()}",
        rng.choice(SECTION_HEADINGS[:3]),
    ]
    step = max(2, len(paragraphs) // 3)
    heading_index = 3
    for i in range(0, len(paragraphs), step):
        if heading_index < len(SECTION_HEADINGS):
            parts.append(SECTION_HEADINGS[heading_index])
            heading_index += 1
        parts.extend(paragraphs[i : i + step])
    parts.append(SECTION_HEADINGS[-1])

    text = "\n\n".join(parts)
    return {
        "text": text,
        "trl": label,
        "domain": domain["name"],
        "technology_name": rng.choice(domain["tech"]).title(),
        "organization": org,
    }


def generate_dataset(
    samples_per_class: int = 60, seed: int = 42
) -> list[dict[str, Any]]:
    """Generate a balanced synthetic demonstration dataset (labels 1-9)."""
    rng = random.Random(seed)
    records: list[dict[str, Any]] = []
    counter = 0
    for label in range(1, 10):
        for index in range(samples_per_class):
            domain = DOMAINS[(label + index) % len(DOMAINS)]
            record = generate_document(label, domain, rng)
            counter += 1
            record["id"] = f"syn_{counter:05d}"
            record["source"] = "SYNTHETIC_DEMO"
            records.append(record)
    rng.shuffle(records)
    return records
