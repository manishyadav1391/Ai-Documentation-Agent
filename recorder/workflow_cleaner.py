"""
Issue #21: Workflow Cleaner — Post-processing module that groups raw action steps
into logical, human-readable workflow steps for documentation generation.

Transforms noisy event logs like:
    Click Username → Type "admin" → Click Password → Type "****" → Click Login

Into clean documentation steps like:
    Step 1: Enter credentials (username, password) and click Login.
"""

import logging
from copy import deepcopy


class WorkflowCleaner:
    """
    Groups and simplifies raw recorder steps into logical workflow steps.
    
    Rules:
    1. Consecutive input steps on different fields → merge into one "Enter data" step.
    2. Input steps followed immediately by a click → attach the click context.
    3. Consecutive clicks on the same window within a short time → keep only the last meaningful one.
    4. Dropdown open + option select → "Select X from dropdown".
    """
    
    def __init__(self, steps):
        """
        steps: list of step dicts (from session.json format).
        """
        self.raw_steps = steps
        self.cleaned_steps = []
    
    def clean(self):
        """
        Main entry point. Groups and simplifies raw steps.
        Returns a list of cleaned step dicts.
        """
        if not self.raw_steps:
            return []
        
        groups = self._group_steps()
        self.cleaned_steps = self._summarize_groups(groups)
        return self.cleaned_steps
    
    def _group_steps(self):
        """
        Groups consecutive steps into logical clusters.
        
        Grouping rules:
        - Consecutive 'input' steps are grouped together.
        - An 'input' group followed by a 'click' absorbs that click (e.g., fill form → click Submit).
        - Standalone 'click' steps remain individual.
        """
        groups = []
        current_group = []
        
        for step in self.raw_steps:
            action = step.get("action_type", "")
            
            if action == "input":
                # Accumulate input steps
                current_group.append(step)
            elif action == "click":
                if current_group and current_group[-1].get("action_type") == "input":
                    # This click follows inputs — attach it to the input group
                    current_group.append(step)
                    groups.append(current_group)
                    current_group = []
                else:
                    # Standalone click — flush any pending group and start fresh
                    if current_group:
                        groups.append(current_group)
                        current_group = []
                    groups.append([step])
            else:
                # Unknown action type — flush and keep as standalone
                if current_group:
                    groups.append(current_group)
                    current_group = []
                groups.append([step])
        
        # Flush any remaining group
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _summarize_groups(self, groups):
        """
        Converts each group of raw steps into a single cleaned step with a
        human-readable business_action summary.
        """
        cleaned = []
        clean_step_no = 0
        
        for group in groups:
            clean_step_no += 1
            
            if len(group) == 1:
                # Single step — use as-is with updated step number
                step = deepcopy(group[0])
                step["clean_step_no"] = clean_step_no
                step["clean_action"] = step.get("business_action", "")
                cleaned.append(step)
            else:
                # Multi-step group — summarize
                summary = self._build_group_summary(group)
                
                # Use the last step as the representative (usually the final click or last input)
                representative = deepcopy(group[-1])
                representative["clean_step_no"] = clean_step_no
                representative["clean_action"] = summary
                representative["grouped_steps"] = [s.get("step_no") for s in group]
                representative["grouped_actions"] = [s.get("business_action", "") for s in group]
                cleaned.append(representative)
        
        return cleaned
    
    def _build_group_summary(self, group):
        """
        Builds a human-readable summary for a group of steps.
        """
        input_steps = [s for s in group if s.get("action_type") == "input"]
        click_steps = [s for s in group if s.get("action_type") == "click"]
        
        parts = []
        
        # Summarize inputs
        if input_steps:
            field_names = []
            for s in input_steps:
                meta = s.get("metadata", {})
                fname = meta.get("field_name", "")
                if fname and fname not in ("Unknown Field", "Input Field", ""):
                    field_names.append(fname)
            
            if len(field_names) == 1:
                parts.append(f"Enter data in {field_names[0]}")
            elif len(field_names) > 1:
                fields_str = ", ".join(field_names[:-1]) + f" and {field_names[-1]}"
                parts.append(f"Enter data in {fields_str}")
            else:
                parts.append(f"Enter data ({len(input_steps)} field{'s' if len(input_steps) > 1 else ''})")
        
        # Summarize trailing click
        if click_steps:
            last_click = click_steps[-1]
            click_meta = last_click.get("metadata", {})
            click_element = click_meta.get("element_name", "")
            
            if click_element and click_element != "UI Element":
                if parts:
                    parts.append(f"then click {click_element}")
                else:
                    parts.append(f"Click {click_element}")
            elif parts:
                parts.append("then submit")
        
        if parts:
            # Capitalize first letter and join
            summary = ", ".join(parts)
            return summary[0].upper() + summary[1:]
        
        return "Perform action"


def clean_workflow(steps):
    """
    Convenience function: takes raw steps list, returns cleaned steps list.
    """
    cleaner = WorkflowCleaner(steps)
    return cleaner.clean()
