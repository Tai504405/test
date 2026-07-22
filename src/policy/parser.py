import re
from typing import List
from src.policy.models import AccountPolicy, PolicyValidationError

def parse_policy_md(file_path: str) -> AccountPolicy:
    """Parses a Markdown policy file into an AccountPolicy model.

    Raises PolicyValidationError with actionable messages if any required sections
    or properties are missing or malformed.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        raise PolicyValidationError(
            f"Policy file not found at: {file_path}\n"
            f"Action: Verify that the file exists at the specified path."
        )
    except Exception as e:
        raise PolicyValidationError(
            f"Error reading policy file: {str(e)}\n"
            f"Action: Check file permissions and formatting."
        )

    if not content.strip():
        raise PolicyValidationError(
            "The policy file is empty.\n"
            "Action: Provide valid Markdown content with account configuration rules."
        )

    lines = content.splitlines()

    # 1. Identify headers and split into sections
    main_header_pattern = re.compile(r"^#\s+(?:Account Policy:|Policy:|Account:)?\s*(.+)$", re.IGNORECASE)
    
    account_id = None
    main_header_line_idx = -1

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") and not stripped.startswith("##"):
            match = main_header_pattern.match(stripped)
            if match:
                account_id = match.group(1).strip()
                main_header_line_idx = idx
                break

    if not account_id:
        raise PolicyValidationError(
            "Missing main account header.\n"
            "Action: Ensure the Markdown file starts with a Level 1 heading containing the Account ID.\n"
            "Example: '# Policy: threads_10xlab' or '# Account Policy: facebook_tech'."
        )

    # 2. Extract metadata and identify subheadings
    # Metadata is parsed from the lines between the main header and the first subheading.
    preamble_lines = []
    first_subheading_idx = len(lines)

    for idx in range(main_header_line_idx + 1, len(lines)):
        line = lines[idx]
        stripped = line.strip()
        # Subheading can start with '#', '##', or '###' if it's the next section
        if stripped.startswith("#"):
            first_subheading_idx = idx
            break
        preamble_lines.append(line)

    preamble_text = "\n".join(preamble_lines)

    # Extract Threshold
    threshold_match = re.search(r"(?:^|\n)[-*\s]*Threshold:\s*([^\n]+)", preamble_text, re.IGNORECASE)
    if not threshold_match:
        raise PolicyValidationError(
            f"Missing 'Threshold' metadata in account policy '{account_id}'.\n"
            "Action: Add a 'Threshold: <float>' line under the main header (e.g., 'Threshold: 0.8')."
        )
    try:
        threshold = float(threshold_match.group(1).strip())
    except ValueError:
        raise PolicyValidationError(
            f"Invalid 'Threshold' value in account policy '{account_id}'.\n"
            "Action: Ensure 'Threshold' is a valid decimal number (e.g., 'Threshold: 0.85')."
        )

    # Extract Model Route
    model_route_match = re.search(r"(?:^|\n)[-*\s]*Model\s*Route:\s*([^\n]+)", preamble_text, re.IGNORECASE)
    if not model_route_match:
        raise PolicyValidationError(
            f"Missing 'Model Route' metadata in account policy '{account_id}'.\n"
            "Action: Add a 'Model Route: <string>' line under the main header (e.g., 'Model Route: gemini-1.5-flash')."
        )
    model_route = model_route_match.group(1).strip()

    # 3. Parse sections by looking at all subheadings
    sections = {}
    current_section = None
    current_section_lines = []

    for idx in range(first_subheading_idx, len(lines)):
        line = lines[idx]
        stripped = line.strip()
        
        # A heading line starts with one or more '#'
        if stripped.startswith("#"):
            if current_section:
                sections[current_section] = current_section_lines
            # Parse section name, stripping hashes and whitespace
            heading_title = re.sub(r"^#+\s*", "", stripped).strip().lower()
            current_section = heading_title
            current_section_lines = []
        else:
            if current_section is not None:
                current_section_lines.append(line)

    if current_section:
        sections[current_section] = current_section_lines

    # Validate that required sections are present
    required_sections = ["goal", "constraints", "examples", "rubric"]
    for req in required_sections:
        if req not in sections:
            raise PolicyValidationError(
                f"Missing required section '## {req.capitalize()}' in account policy '{account_id}'.\n"
                f"Action: Add a '## {req.capitalize()}' section to the Markdown file."
            )

    # Parse Goal
    goal = "\n".join(sections["goal"]).strip()
    if not goal:
        raise PolicyValidationError(
            f"The '## Goal' section is empty in account policy '{account_id}'.\n"
            "Action: Write a brief description of the goal for this account under '## Goal'."
        )

    # Parse lists helper
    def parse_list_items(section_name: str, section_lines: List[str]) -> List[str]:
        items = []
        for line in section_lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Match lists starting with -, *, or + followed by whitespace
            match = re.match(r"^[-*+]\s+(.+)$", stripped)
            if match:
                items.append(match.group(1).strip())
        
        if not items:
            raise PolicyValidationError(
                f"The '## {section_name.capitalize()}' section does not contain any valid list items in account policy '{account_id}'.\n"
                f"Action: Add at least one bullet point starting with '-', '*', or '+' under '## {section_name.capitalize()}'."
            )
        return items

    constraints = parse_list_items("constraints", sections["constraints"])
    examples = parse_list_items("examples", sections["examples"])
    rubric = parse_list_items("rubric", sections["rubric"])

    return AccountPolicy(
        account_id=account_id,
        goal=goal,
        constraints=constraints,
        examples=examples,
        rubric=rubric,
        threshold=threshold,
        model_route=model_route
    )
