"""Generate the synthetic two-page Bengaluru lease PDF using the installed pypdf."""
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


OUTPUT = Path(__file__).with_name("sample_bengaluru_lease.pdf")
PAGES = [
    [
        "SAMPLE BENGALURU RESIDENTIAL TENANCY AGREEMENT",
        "Synthetic example for testing LeaseLens. Parties and terms are fictional.",
        "",
        "Clause 1.1 (Monthly Rent): Monthly rent of INR 30,000 is payable by the",
        "5th day of each month by bank transfer to the landlord's nominated account.",
        "",
        "Clause 3.1 (Security Deposit): The tenant shall pay INR 1,50,000, equal to",
        "five months of rent. The deposit is refundable at handover, subject to any",
        "itemised deductions supported by the agreement and applicable law.",
        "",
        "Clause 5.2 (Lock-in & Notice Period): The tenancy has a six-month lock-in",
        "period. After the lock-in period, either party must give two months' written",
        "notice to end the tenancy, subject to applicable law.",
    ],
    [
        "SAMPLE BENGALURU RESIDENTIAL TENANCY AGREEMENT (continued)",
        "",
        "Clause 7.4 (Mandatory Painting Deduction): At move-out, the landlord may",
        "deduct INR 35,000 for full-flat repainting without contractor bills. This is",
        "a fictional sample clause and does not establish that the deduction is valid.",
        "",
        "Clause 9.2 (Appliance Maintenance): The tenant bears the full cost of an",
        "aging geyser heating coil burnout, subject to evidence, the cause of damage,",
        "the terms of the agreement, and applicable state law.",
        "",
        "Sample only. Model Tenancy Act references in LeaseLens are illustrative.",
        "Confirm applicable Karnataka law and all facts with a qualified lawyer.",
    ],
]


def pdf_string(value: str) -> bytes:
    escaped = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return escaped.encode("ascii")


def main() -> None:
    writer = PdfWriter()
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    for lines in PAGES:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
        })
        commands = [b"BT /F1 11 Tf 48 744 Td 15 TL"]
        for line in lines:
            commands.append(b"(" + pdf_string(line) + b") Tj T*")
        commands.append(b"ET")
        stream = DecodedStreamObject()
        stream.set_data(b"\n".join(commands))
        page[NameObject("/Contents")] = writer._add_object(stream)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("wb") as pdf_file:
        writer.write(pdf_file)
    print(f"Generated {OUTPUT} ({len(PAGES)} pages)")


if __name__ == "__main__":
    main()
