# Milestone 3 real-corpus chunk audit

Generated from the 8 documents in `data/corpus/` after boilerplate stripping and ingestion into the main database. Token counts are the ingestion-time approximate tokenizer counts stored in `chunks.token_count`. Three chunks per document were selected with a fixed random seed (`20261025`) so the sample is reproducible.

## Summary

| Document | Pages | Chunks | Min | p50 | p90 | Max | Mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `21 CFR Part 11 (up to date as of 10-21-2026).pdf` | 6 | 11 | 92 | 348 | 497 | 499 | 331.9 |
| `21 CFR Part 211 (up to date as of 10-21-2026).pdf` | 29 | 50 | 26 | 392 | 487 | 495 | 331.3 |
| `21 CFR Part 58 (up to date as of 10-21-2026).pdf` | 19 | 33 | 89 | 421 | 489 | 500 | 332.3 |
| `7883441_DataIntegrity.pdf` | 17 | 33 | 60 | 381 | 484 | 494 | 325.3 |
| `osha-1910-1200-hazard-communication.pdf` | 20 | 40 | 44 | 377 | 476 | 494 | 337.9 |
| `osha-1910-1450-lab-standard.pdf` | 8 | 14 | 128 | 361.5 | 500 | 500 | 339.5 |
| `Part-11--Electronic-Records--Electronic-Signatures---Scope-and-Application-(PDF).pdf` | 12 | 20 | 84 | 433 | 485 | 490 | 348.2 |
| `Process-Validation--General-Principles-and-Practices.pdf` | 22 | 37 | 60 | 423 | 493 | 499 | 335.1 |

## Random chunk samples

### `21 CFR Part 11 (up to date as of 10-21-2026).pdf`

- Title: 21 CFR Part 11: Electronic Records; Electronic Signatures
- Agency / type / year / version: FDA / regulation / 2026 / eCFR up to date as of 2026-10-21
- Chunks: 11; token min/p50/p90/max/mean: 92/348/497/499/331.9

**Chunk 3** (page 3, 457 tokens)

```text
§ 11.2 Implementation. § 11.3 Definitions. (a) For records required to be maintained but not submitted to the agency, persons may use electronic
records in lieu of paper records or electronic signatures in lieu of traditional signatures, in whole or in part,
provided that the requirements of this part are met. (b) For records submitted to the agency, persons may use electronic records in lieu of paper records or
electronic signatures in lieu of traditional signatures, in whole or in part, provided that:
(1) The requirements of this part are met; and
(2) The document or parts of a document to be submitted have been identified in public docket No. 92S-0251 as being the type of submission the agency accepts in electronic form. This docket will
identify specifically what types of documents or parts of documents are acceptable for submission
in electronic form without paper records and the agency receiving unit(s) (e.g., specific center, office,
division, branch) to which such submissions may be made. Documents to agency receiving unit(s)
not specified in the public docket will not be considered as official if they are submitted in electronic
form; paper forms of such documents will be considered as official and must accompany any
electronic records. Persons are expected to consult with the intended agency receiving unit for
details on how (e.g., method of transmission, media, file formats, and technical protocols) and
whether to proceed with the electronic submission. (a) The definitions and interpretations of terms contained in section 201 of the act apply to those terms when
used in this part. (b) The following definitions of terms also apply to this part:
(1) Act means the Federal Food, Drug, and Cosmetic Act (secs. 201-903 (21 U.S.C. 321-393)). (2) Agency means the Food and Drug Administration. (3) Biometrics means a method of verifying an individual's identity based on measurement of the
individual's physical feature(s) or repeatable action(s) where those features and/or actions are both
unique to that individual and measurable. (4) Closed system means an environment in which system access is controlled by persons who are
responsible for the content of electronic records that are on the system.
```

**Chunk 6** (page 4, 159 tokens)

```text
(g) Use of authority checks to ensure that only authorized individuals can use the system, electronically sign a
record, access the operation or computer system input or output device, alter a record, or perform the
operation at hand. (h) Use of device (e.g., terminal) checks to determine, as appropriate, the validity of the source of data input
or operational instruction. (i) Determination that persons who develop, maintain, or use electronic record/electronic signature systems
have the education, training, and experience to perform their assigned tasks. (j) The establishment of, and adherence to, written policies that hold individuals accountable and responsible
for actions initiated under their electronic signatures, in order to deter record and signature falsification. (k) Use of appropriate controls over systems documentation including:
```

**Chunk 10** (page 6, 92 tokens)

```text
(d) Use of transaction safeguards to prevent unauthorized use of passwords and/or identification codes, and
to detect and report in an immediate and urgent manner any attempts at their unauthorized use to the
system security unit, and, as appropriate, to organizational management. (e) Initial and periodic testing of devices, such as tokens or cards, that bear or generate identification code or
password information to ensure that they function properly and have not been altered in an unauthorized
manner.
```

### `21 CFR Part 211 (up to date as of 10-21-2026).pdf`

- Title: 21 CFR Part 211: Current Good Manufacturing Practice for Finished Pharmaceuticals
- Agency / type / year / version: FDA / regulation / 2026 / eCFR up to date as of 2026-10-21
- Chunks: 50; token min/p50/p90/max/mean: 26/392/487/495/331.3

**Chunk 12** (page 9, 189 tokens)

```text
A backup file of data entered into the computer or related
system shall be maintained except where certain data, such as calculations performed in connection with
laboratory analysis, are eliminated by computerization or other automated processes. In such instances a
written record of the program shall be maintained along with appropriate validation data. Hard copy or
alternative systems, such as duplicates, tapes, or microfilm, designed to assure that backup data are
exact and complete and that it is secure from alteration, inadvertent erasures, or loss shall be maintained. (c) Such automated equipment used for performance of operations addressed by §§ 211.101(c) or (d),
211.103, 211.182, or 211.188(b)(11) can satisfy the requirements included in those sections relating to
the performance of an operation by one person and checking by another person if such equipment is
used in conformity with this section, and one person checks that the equipment properly performed the
operation.
```

**Chunk 43** (page 25, 161 tokens)

```text
Reasonable variations may be permitted,
however, in the amount of components necessary for the preparation in the dosage form, provided
they are justified in the master production and control records;
(5) A statement concerning any calculated excess of component;
(6) A statement of theoretical weight or measure at appropriate phases of processing;
(7) A statement of theoretical yield, including the maximum and minimum percentages of theoretical
yield beyond which investigation according to § 211.192 is required;
(8) A description of the drug product containers, closures, and packaging materials, including a
specimen or copy of each label and all other labeling signed and dated by the person or persons
responsible for approval of such labeling;
(9) Complete manufacturing and control instructions, sampling and testing procedures, specifications,
special notations, and precautions to be followed.
```

**Chunk 46** (page 27, 162 tokens)

```text
(b) Complete records shall be maintained of any modification of an established method employed in testing. Such records shall include the reason for the modification and data to verify that the modification
produced results that are at least as accurate and reliable for the material being tested as the established
method. (c) Complete records shall be maintained of any testing and standardization of laboratory reference
standards, reagents, and standard solutions. (d) Complete records shall be maintained of the periodic calibration of laboratory instruments, apparatus,
gauges, and recording devices required by § 211.160(b)(4). (e) Complete records shall be maintained of all stability testing performed in accordance with § 211.166. [1] Copies may be obtained from: AOAC INTERNATIONAL, 481 North Frederick Ave., suite 500, Gaithersburg,
MD 20877.
```

### `21 CFR Part 58 (up to date as of 10-21-2026).pdf`

- Title: 21 CFR Part 58: Good Laboratory Practice for Nonclinical Laboratory Studies
- Agency / type / year / version: FDA / regulation / 2026 / eCFR up to date as of 2026-10-21
- Chunks: 33; token min/p50/p90/max/mean: 89/421/489/500/332.3

**Chunk 4** (page 4, 489 tokens)

```text
(16) A Product Development Protocol for a Medical Device, described in section 515 of the act. (17) Data and information regarding a medical device submitted as part of the procedures for classifying
such devices, described in part 860. (18) Data and information regarding a medical device submitted as part of the procedures for
establishing, amending, or repealing a performance standard for such devices, described in part 861. (19) Data and information regarding an electronic product submitted as part of the procedures for
obtaining an exemption from notification of a radiation safety defect or failure of compliance with a
radiation safety performance standard, described in subpart D of part 1003. (20) Data and information regarding an electronic product submitted as part of the procedures for
establishing, amending, or repealing a standard for such product, described in section 358 of the
Public Health Service Act. (21) Data and information regarding an electronic product submitted as part of the procedures for
obtaining a variance from any electronic product performance standard as described in § 1010.4. (22) Data and information regarding an electronic product submitted as part of the procedures for
granting, amending, or extending an exemption from any electronic product performance standard,
as described in § 1010.5. (23) A premarket notification for a food contact substance, described in part 170, subpart D, of this
chapter. (f) Sponsor means:
(1) A person who initiates and supports, by provision of financial or other resources, a nonclinical
laboratory study;
(2) A person who submits a nonclinical study to the Food and Drug Administration in support of an
application for a research or marketing permit; or
(3) A testing facility, if it both initiates and actually conducts the study. (g) Testing facility means a person who actually conducts a nonclinical laboratory study, i.e., actually uses the
test article in a test system. Testing facility includes any establishment required to register under section
510 of the act that conducts nonclinical laboratory studies and any consulting laboratory described in
section 704 of the act that conducts such studies. Testing facility encompasses only those operational
units that are being or have been used to conduct nonclinical laboratory studies. (h) Person includes an individual, partnership, corporation, association, scientific or academic establishment,
government agency, or organizational unit thereof, and any other legal entity. (i) Test system means any animal, plant, microorganism, or subparts thereof to which the test or control
article is administered or added for study.
```

**Chunk 26** (page 16, 421 tokens)

```text
[43 FR 60013, Dec. 22, 1978, as amended at 52 FR 33781, Sept. 4, 1987; 54 FR 9039, Mar. 3, 1989]
Subpart K—Disqualification of Testing Facilities
§ 58.200 Purpose. § 58.202 Grounds for disqualification. The Commissioner may disqualify a testing facility upon finding all of the following:
(c) Wet specimens (except those specimens obtained from mutagenicity tests and wet specimens of blood,
urine, feces, and biological fluids), samples of test or control articles, and specially prepared material,
which are relatively fragile and differ markedly in stability and quality during storage, shall be retained only
as long as the quality of the preparation affords evaluation. In no case shall retention be required for
longer periods than those set forth in paragraphs (a) and (b) of this section. (d) The master schedule sheet, copies of protocols, and records of quality assurance inspections, as required
by § 58.35(c) shall be maintained by the quality assurance unit as an easily accessible system of records
for the period of time specified in paragraphs (a) and (b) of this section. (e) Summaries of training and experience and job descriptions required to be maintained by § 58.29(b) may
be retained along with all other testing facility employment records for the length of time specified in
paragraphs (a) and (b) of this section. (f) Records and reports of the maintenance and calibration and inspection of equipment, as required by §
58.63(b) and (c), shall be retained for the length of time specified in paragraph (b) of this section. (g) Records required by this part may be retained either as original records or as true copies such as
photocopies, microfilm, microfiche, or other accurate reproductions of the original records. (h) If a facility conducting nonclinical testing goes out of business, all raw data, documentation, and other
material specified in this section shall be transferred to the archives of the sponsor of the study. The Food
and Drug Administration shall be notified in writing of such a transfer.
```

**Chunk 28** (page 17, 449 tokens)

```text
§ 58.204 Notice of and opportunity for hearing on proposed disqualification. § 58.206 Final order on disqualification. § 58.210 Actions upon disqualification. [43 FR 60013, Dec. 22, 1978, as amended at 59 FR 13200, Mar. 21, 1994]
(c) Other lesser regulatory actions (e.g., warnings or rejection of individual studies) have not been or will
probably not be adequate to achieve compliance with the good laboratory practice regulations. (a) Whenever the Commissioner has information indicating that grounds exist under § 58.202 which in his
opinion justify disqualification of a testing facility, he may issue to the testing facility a written notice
proposing that the facility be disqualified. (b) A hearing on the disqualification shall be conducted in accordance with the requirements for a regulatory
hearing set forth in part 16 of this chapter. (a) If the Commissioner, after the regulatory hearing, or after the time for requesting a hearing expires without
a request being made, upon an evaluation of the administrative record of the disqualification proceeding,
makes the findings required in § 58.202, he shall issue a final order disqualifying the facility. Such order
shall include a statement of the basis for that determination. Upon issuing a final order, the Commissioner
shall notify (with a copy of the order) the testing facility of the action. (b) If the Commissioner, after a regulatory hearing or after the time for requesting a hearing expires without a
request being made, upon an evaluation of the administrative record of the disqualification proceeding,
does not make the findings required in § 58.202, he shall issue a final order terminating the
disqualification proceeding. Such order shall include a statement of the basis for that determination. Upon issuing a final order the Commissioner shall notify the testing facility and provide a copy of the
order. (a) Once a testing facility has been disqualified, each application for a research or marketing permit, whether
approved or not, containing or relying upon any nonclinical laboratory study conducted by the disqualified
testing facility may be examined to determine whether such study was or would be essential to a
decision. If it is determined that a study was or would be essential, the Food and Drug Administration
shall also determine whether the study is acceptable, notwithstanding the disqualification of the facility.
```

### `7883441_DataIntegrity.pdf`

- Title: Data Integrity and Compliance With Drug CGMP: Questions and Answers
- Agency / type / year / version: FDA / guidance / 2018 / Final December 2018
- Chunks: 33; token min/p50/p90/max/mean: 60/381/484/494/325.3

**Chunk 8** (page 4, 138 tokens)

```text
17. Is FDA allowed to look at electronic records? ........................................................................... 12
18. How does FDA recommend data integrity problems be addressed? ...................................... 12
```

**Chunk 9** (page 5, 480 tokens)

```text
Data Integrity and Compliance With Drug CGMP
Questions and Answers
Guidance for Industry1
This guidance represents the current thinking of the Food and Drug Administration (FDA or Agency) on
this topic. It does not establish any rights for any person and is not binding on FDA or the public. You can
use an alternative approach if it satisfies the requirements of the applicable statutes and regulations. To
discuss an alternative approach, contact the FDA office responsible for this guidance as listed on the title
page. I. INTRODUCTION
The purpose of this guidance is to clarify the role of data integrity in current good manufacturing
practice (CGMP) for drugs, as required in 21 CFR parts 210, 211, and 212. Unless otherwise
noted, the term CGMP in this guidance refers to CGMPs for drugs (including biologics). FDA’s
authority for CGMP comes from section 501(a)(2)(B) of the Federal Food, Drug, and Cosmetic
Act (FD&C Act). Part 210 covers Current Good Manufacturing Practice in Manufacturing,
Processing, Packing, or Holding of Drugs; General; part 211 covers Current Good
Manufacturing Practice for Finished Pharmaceuticals; and part 212 covers Current Good
Manufacturing Practice for Positron Emission Tomography (PET) Drugs. All citations to parts
211 and 212 in this document pertain to finished pharmaceuticals and PET drugs, but these
requirements are also consistent with Agency guidance on CGMP for active pharmaceutical
ingredients with respect to data integrity.2 This guidance provides the Agency’s current thinking
on the creation and handling of data in accordance with CGMP requirements. FDA expects that all data be reliable and accurate (see the “Background” section). CGMP
regulations and guidance allow for flexible and risk-based strategies to prevent and detect data
integrity issues. Firms should implement meaningful and effective strategies to manage their data
integrity risks based on their process understanding and knowledge management of technologies
and business models.3
Meaningful and effective strategies should consider the design, operation, and monitoring of
systems and controls based on risk to patient, process, and product. Management’s involvement
1 This guidance has been prepared by the Office of Pharmaceutical Quality and the Office of Compliance in the
Center for Drug Evaluation and Research in cooperation with the Center for Biologics Evaluation and Research, the
Center for Veterinary Medicine, and the Office of Regulatory Affairs at the Food and Drug Administration. 2 See the International Council for Harmonisation (ICH) guidance for industry Q7 Good Manufacturing Practice
Guide for Active Pharmaceutical Ingredients. We update guidances periodically.
```

**Chunk 23** (page 12, 165 tokens)

```text
See the audit trail definition in 1.c. above for further information on audit trails. 9. Can electronic copies be used as accurate reproductions of paper or electronic
records? Yes. Electronic copies can be used as true copies of paper or electronic records, provided the
copies preserve the content and meaning of the original record, which includes all metadata
12 See guidance for industry Quality Systems Approach to Pharmaceutical CGMP Regulations . See also guidance
for industry Contract Manufacturing Arrangements for Drugs: Quality Agreements for information about auditing
as it relates to contract facilities. 13 Risks to data include, but are not limited to, the potential to be deleted, amended, or excluded without
authorization or without detection. Examples of audit trails that may be appropriate to review on a risk-based
frequency include audit trails that capture instrument operational status, instrument communication logs, and alert
records.
```

### `osha-1910-1200-hazard-communication.pdf`

- Title: 29 CFR 1910.1200: Hazard Communication
- Agency / type / year / version: OSHA / regulation / 2026 / OSHA web version saved October 2026
- Chunks: 40; token min/p50/p90/max/mean: 44/377/476/494/337.9

**Chunk 3** (page 2, 375 tokens)

```text
1910.1200(b)(5)
This section does not require labeling of the following chemicals:
1910.1200(b)(5)(i)
Any pesticide as such term is defined in the Federal Insecticide, Fungicide, and Rodenticide Act (7 U.S.C. 136 et seq.), when
subject to the labeling requirements of that Act and labeling regulations issued under that Act by the Environmental Protection
Agency;
1910.1200(b)(5)(ii)
Any chemical substance or mixture as such terms are defined in the Toxic Substances Control Act (15 U.S.C. 2601 et seq.), when
subject to the labeling requirements of that Act and labeling regulations issued under that Act by the Environmental Protection
Agency. 1910.1200(b)(5)(iii)
Any food, food additive, color additive, drug, cosmetic, or medical or veterinary device or product, including materials
intended for use as ingredients in such products (e.g., flavors and fragrances), as such terms are defined in the Federal Food,
Drug, and Cosmetic Act (21 U.S.C. 301 et seq.) or the Virus-Serum-Toxin Act of 1913 (21 U.S.C. 151 et seq.), and regulations
issued under those Acts, when they are subject to the labeling requirements under those Acts by either the Food and Drug
Administration or the Department of Agriculture;
1910.1200(b)(5)(iv)
Any distilled spirits (beverage alcohols), wine, or malt beverage intended for nonindustrial use, as such terms are defined in the
Federal Alcohol Administration Act (27 U.S.C. 201 et seq.) and regulations issued under that Act, when subject to the labeling
requirements of that Act and labeling regulations issued under that Act by the Bureau of Alcohol, Tobacco, Firearms and
Explosives;
```

**Chunk 21** (page 10, 250 tokens)

```text
1910.1200(f)(12)
Small container labelling. 1910.1200(f)(12)(i)
This paragraph applies where the chemical manufacturer, importer, or distributor can demonstrate that it is not feasible to use
pull-out labels, fold-back labels, or tags containing the full label information required by paragraph (f)(1) of this section. 1910.1200(f)(12)(ii)
For a container less than or equal to 100 ml capacity, the chemical manufacturer, importer, or distributor must include, at a
minimum, the following information on the label of the container:
1910.1200(f)(12)(ii)(A)
Product identifier;
1910.1200(f)(12)(ii)(B)
Pictogram(s);
1910.1200(f)(12)(ii)(C)
Signal word;
1910.1200(f)(12)(ii)(D)
Chemical manufacturerʼs name and phone number; and
1910.1200(f)(12)(ii)(E)
A statement that the full label information for the hazardous chemical is provided on the immediate outer package. 1910.1200(f)(12)(iii)
```

**Chunk 28** (page 14, 446 tokens)

```text
Employers shall provide employees with effective information and training on hazardous chemicals in their work area at the
time of their initial assignment, and whenever a new chemical hazard the employees have not previously been trained about is
introduced into their work area. Information and training may be designed to cover categories of hazards (e.g., flammability,
carcinogenicity) or specific chemicals. Chemical-specific information must always be available through labels and safety data
sheets. 1910.1200(h)(2)
Information. Employees shall be informed of:
1910.1200(h)(2)(i)
The requirements of this section;
1910.1200(h)(2)(ii)
Any operations in their work area where hazardous chemicals are present; and,
1910.1200(h)(2)(iii)
The location and availability of the written hazard communication program, including the required list(s) of hazardous
chemicals, and safety data sheets required by this section. 1910.1200(h)(3)
Training. Employee training shall include at least:
1910.1200(h)(3)(i)
Methods and observations that may be used to detect the presence or release of a hazardous chemical in the work area (such
as monitoring conducted by the employer, continuous monitoring devices, visual appearance or odor of hazardous chemicals
when being released, etc.);
1910.1200(h)(3)(ii)
The physical, health, simple asphyxiation, combustible dust, and pyrophoric gas hazards, as well as hazards not otherwise
classified, of the chemicals in the work area;
1910.1200(h)(3)(iii)
The measures employees can take to protect themselves from these hazards, including specific procedures the employer has
implemented to protect employees from exposure to hazardous chemicals, such as appropriate work practices, emergency
procedures, and personal protective equipment to be used; and,
1910.1200(h)(3)(iv)
The details of the hazard communication program developed by the employer, including an explanation of the labels received
on shipped containers and the workplace labeling system used by their employer; the safety data sheet, including the order of
information and how employees can obtain and use the appropriate hazard information. 1910.1200(i)
Trade secrets.
```

### `osha-1910-1450-lab-standard.pdf`

- Title: 29 CFR 1910.1450: Occupational Exposure to Hazardous Chemicals in Laboratories
- Agency / type / year / version: OSHA / regulation / 2026 / OSHA web version saved October 2026
- Chunks: 14; token min/p50/p90/max/mean: 128/361.5/500/500/339.5

**Chunk 1** (page 1, 147 tokens)

```text
1910.1450(a)(3)(ii)
Laboratory uses of hazardous chemicals which provide no potential for employee exposure. Examples of such conditions might
include:
1910.1450(a)(3)(ii)(A)
Procedures using chemically-impregnated test media such as Dip-and-Read tests where a reagent strip is dipped into the
specimen to be tested and the results are interpreted by comparing the color reaction to a color chart supplied by the
manufacturer of the test strip; and
1910.1450(a)(3)(ii)(B)
Commercially prepared kits such as those used in performing pregnancy tests in which all of the reagents needed to conduct
the test are contained in the kit. 1910.1450(b)
```

**Chunk 6** (page 4, 246 tokens)

```text
1910.1450(d)(3)
Termination of monitoring. Monitoring may be terminated in accordance with the relevant standard. 1910.1450(d)(4)
Employee notification of monitoring results. The employer shall, within 15 working days after the receipt of any monitoring
results, notify the employee of these results in writing either individually or by posting results in an appropriate location that is
accessible to employees. 1910.1450(e)
Chemical hygiene plan - General. (Appendix A of this section is non-mandatory but provides guidance to assist employers in
the development of the Chemical Hygiene Plan). 1910.1450(e)(1)
Where hazardous chemicals as defined by this standard are used in the workplace, the employer shall develop and carry out
the provisions of a written Chemical Hygiene Plan which is:
1910.1450(e)(1)(i)
Capable of protecting employees from health hazards associated with hazardous chemicals in that laboratory and
1910.1450(e)(1)(ii)
Capable of keeping exposures below the limits specified in paragraph (c) of this section. 1910.1450(e)(2)
The Chemical Hygiene Plan shall be readily available to employees, employee representatives and, upon request, to the
Assistant Secretary.
```

**Chunk 10** (page 6, 235 tokens)

```text
Such consultation
shall be for the purpose of determining the need for a medical examination. 1910.1450(g)(2)
All medical examinations and consultations shall be performed by or under the direct supervision of a licensed physician and
shall be provided without cost to the employee, without loss of pay and at a reasonable time and place. 1910.1450(g)(3)
Information provided to the physician. The employer shall provide the following information to the physician:
1910.1450(g)(3)(i)
The identity of the hazardous chemical(s) to which the employee may have been exposed;
1910.1450(g)(3)(ii)
A description of the conditions under which the exposure occurred including quantitative exposure data, if available; and
1910.1450(g)(3)(iii)
A description of the signs and symptoms of exposure that the employee is experiencing, if any. 1910.1450(g)(4)
Physician's written opinion. 1910.1450(g)(4)(i)
For examination or consultation required under this standard, the employer shall obtain a written opinion from the examining
physician which shall include the following:
```

### `Part-11--Electronic-Records--Electronic-Signatures---Scope-and-Application-(PDF).pdf`

- Title: Part 11, Electronic Records; Electronic Signatures - Scope and Application
- Agency / type / year / version: FDA / guidance / 2003 / Final September 2003
- Chunks: 20; token min/p50/p90/max/mean: 84/433/485/490/348.2

**Chunk 2** (page 3, 475 tokens)

```text
TABLE OF CONTENTS
I. INTRODUCTION............................................................................................................. 1
II. BACKGROUND ............................................................................................................... 2
III. DISCUSSION .................................................................................................................... 3
A. Overall Approach to Part 11 Requirements................................ ................................ ......... 3
B. Details of Approach – Scope of Part 11................................
```

**Chunk 11** (page 7, 490 tokens)

```text
As described in more detail below, the approach outlined in this guidance is based on three main 116
elements: 117
•  Part 11 will be interpreted narrowly; we are now clarifying that fewer records will be 119
considered subject to part 11. 120
•  For those records that remain subject to part 11, we intend to exercise enforcement 121
discretion with regard to part 11 requirements for validation, audit trails, record retention, 122
and record copying in the manner described in this guidance and with regard to all part 11 123
requirements for systems that were operational before the effective date of part 11 (also 124
known as legacy systems).  125
•  We will enforce all predicate rule requirements, including predicate rule record and 126
recordkeeping requirements. 127
It is important to note that FDA's exercise of enforcement discretion as described in this 128
guidance is limited to specified part 11 requirements (setting aside legacy systems, as to which 129
the extent of enforcement discretion, under certain circumstances, will be more broad).  We 130
intend to enforce all other provisions of part 11 including, but not limited to, certain controls for 131
closed systems in § 11.10.  For example, we intend to enforce provisions related to the following 132
controls and requirements: 133
•  limiting system access to authorized individuals 135
•  use of operational system checks 136
•  use of authority checks 137
•  use of device checks 138
•  determination that persons who develop, maintain, or use electronic systems have the 139
education, training, and experience to perform their assigned tasks 140
•  establishment of and adherence to written policies that hold individuals accountable for 141
actions initiated under their electronic signatures 142
•  appropriate controls over systems documentation 143
•  controls for open systems corresponding to controls for closed systems bulleted above (§ 144
11.30) 145
•  requirements related to electronic signatures (e.g., §§ 11.50, 11.70, 11.100, 11.200, and 146
11.300) 147
We expect continued compliance with these provisions, and we will continue to enforce them.  149
Furthermore, persons must comply with applicable predicate rules, and records that are required 150
to be maintained or submitted must remain secure and reliable in accordance with the predicate 151
rules. 152
B. Details of Approach – Scope of Part 11 154
1.   Narrow Interpretation of Scope  156
We understand that there is some confusion about the scope of part 11.  Some have understood 158
the scope of part 11 to be very broad.  We believe that some of those broad interpretations could 159
```

**Chunk 18** (page 11, 453 tokens)

```text
In each case, we recommend that the copying process used produces copies that preserve the 291
content and meaning of the record.  If you have the ability to search, sort, or trend part 11 292
records, copies given to the Agency should provide the same capability if it is reasonable and 293
technically feasible.  You should allow inspection, review, and copying of records in a human 294
readable form at your site using your hardware and following your established procedures and 295
techniques for accessing records.   296
5. Record Retention  298
The Agency intends to exercise enforcement discretion with regard to the part 11 requirements 300
for the protection of records to enable their accurate and ready retrieval throughout the records 301
retention period (§ 11.10 (c) and any corresponding requirement in §11.30).  Persons must still 302
comply with all applicable predicate rule requirements for record retention and availability (e.g., 303
§§ 211.180(c),(d), 108.25(g), and 108.35(h)).   304
We suggest that your decision on how to maintain records be based on predicate rule 306
requirements and that you base your decision on a justified and documented risk assessment and 307
a determination of the value of the records over time.   308
FDA does not intend to object if you decide to archive required records in electronic format to 310
nonelectronic media such as microfilm, microfiche, and paper, or to a standard electronic file 311
format (examples of such formats include, but are not limited to, PDF, XML, or SGML).  312
Persons must still comply with all predicate rule requirements, and the records themselves and 313
any copies of the required records should preserve their content and meaning.  As long as 314
predicate rule requirements are fully satisfied and the content and meaning of the records are 315
preserved and archived, you can delete the electronic version of the records.  In addition, paper 316
and electronic record and signature components can co-exist (i.e., a hybrid8 situation) as long as 317
predicate rule requirements are met and the content and meaning of those records are preserved. 318
8 Examples of hybrid situations include combinations of paper records (or other nonelectronic media) and electronic
records, paper records and electronic signatures, or handwritten sig natures executed to electronic records.
```

### `Process-Validation--General-Principles-and-Practices.pdf`

- Title: Process Validation: General Principles and Practices
- Agency / type / year / version: FDA / guidance / 2011 / Final January 2011
- Chunks: 37; token min/p50/p90/max/mean: 60/423/493/499/335.1

**Chunk 2** (page 3, 437 tokens)

```text
TABLE OF CONTENTS
I. INTRODUCTION............................................................................................................. 1
II. BACKGROUND ............................................................................................................... 3
A. Process Validation and Drug Quality .......................................................................................... 3
B. Approach to Process Validation ................................................................................................... 4
III.
```

**Chunk 3** (page 3, 491 tokens)

```text
4
III. STATUTORY AND REGULATORY REQUIREMENTS FOR PROCESS
VALIDATION................................................................................................................... 5
IV. RECOMMENDATIONS.................................................................................................. 7
A. General Considerations for Process Validation .......................................................................... 7
B. Stage 1 ― Process Design.............................................................................................................. 8
1. Building and Capturing Process Knowledge and Understanding ................................................... 8
2.
```

**Chunk 30** (page 18, 145 tokens)

```text
A description of the
planned change, a well-justified rationale for the change, an implementation plan, and quality
unit approval before implementation must be documented (§ 211.100). Depending on how the
proposed change might affect product quality, additional process design and process
qualification activities could be warranted.19
Maintenance of the facility, utilities, and equipment is another important aspect of ensuring that a
process remains in control. Once established, qualification status must be maintained through
routine monitoring, maintenance, and calibration procedures and schedules (21 CFR part 211,
19  Certain manufacturing changes may call for formal notification to the Agency before implementation, as directed
by existing regulations (see, e.g., 21 CFR 314.70 and 601.12).
```
