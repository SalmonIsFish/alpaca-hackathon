"""Shariah business-activity screen with confidence scoring.

Screens the traded symbol against a curated universe hand-scored 0-100 against MSCI Islamic
methodology. Unlisted is always FAIL -- an unknown symbol is never an invitation to guess.

Note on `data/malaysian_shariah_databank.json`: that file holds 688 records from the Securities
Commission Malaysia Shariah Advisory Council (`sc-sac-my-2026-05-29`) and is NOT consulted here.
It lists Bursa Malaysia tickers, so it cannot screen a US universe -- AAPL has no SC-SAC
classification. It is retained as evidence of the data-governance pattern (an official regulator
list, versioned and dated) rather than as an input to this gate. Corrected 2026-09-02, when the
docstring and the rejection message below both still implied it was being consulted.
"""

from __future__ import annotations

import json
import os
from typing import Dict, Any


def load_enhanced_universe(path: str = None) -> Dict[str, Any]:
    """Load the enhanced Shariah universe with confidence scores."""
    if path is None:
        # Default to enhanced universe
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        path = os.path.join(base_dir, "data", "shariah_universe_enhanced.json")
    
    # Fallback to basic universe if enhanced doesn't exist
    if not os.path.exists(path):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        path = os.path.join(base_dir, "data", "shariah_universe.json")
    
    with open(path, 'r') as f:
        return json.load(f)


def check_symbol_enhanced(symbol: str, universe: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced Shariah compliance check with confidence scoring.
    
    Returns:
        {
            "status": "PASS" | "FAIL" | "REVIEW",
            "confidence_score": 0-100,
            "reason": detailed explanation,
            "symbol": symbol,
            "methodology": "MSCI_ISLAMIC",
            "financial_ratios": {...} | None
        }
    """
    symbols = universe.get("symbols", universe)  # Handle both formats
    
    if symbol not in symbols:
        return {
            "status": "FAIL",
            "confidence_score": 0,
            "reason": "Not in the curated Shariah universe",
            "symbol": symbol,
            "methodology": "MSCI_ISLAMIC",
            "financial_ratios": None,
            "recommendation": "REJECT"
        }
    
    symbol_data = symbols[symbol]
    
    # Handle enhanced format
    if isinstance(symbol_data, dict) and "confidence_score" in symbol_data:
        confidence = symbol_data["confidence_score"]
        
        # Determine status based on confidence thresholds
        if confidence >= 85:
            status = "PASS"
            reason = f"HIGH CONFIDENCE ({confidence}%): {symbol_data['rationale']}"
        elif confidence >= 70:
            status = "PASS"
            reason = f"MODERATE CONFIDENCE ({confidence}%): {symbol_data['rationale']}"
        elif confidence >= 50:
            status = "REVIEW"
            reason = f"LOW CONFIDENCE ({confidence}%): {symbol_data['rationale']}"
        else:
            status = "FAIL"
            reason = f"INSUFFICIENT CONFIDENCE ({confidence}%): {symbol_data['rationale']}"
        
        return {
            "status": status,
            "confidence_score": confidence,
            "reason": reason,
            "symbol": symbol,
            "methodology": "MSCI_ISLAMIC",
            "financial_ratios": symbol_data.get("financial_ratios"),
            "sector": symbol_data.get("sector"),
            # REVIEW must not read as PASS. pipeline.py gates on `status`, so a REVIEW
            # already blocks there, but this field said "PASS" for it -- a trap for any
            # future caller that gates on `recommendation` instead. Fail closed on both.
            "recommendation": "PASS" if status == "PASS" else "REJECT"
        }
    
    # Handle basic format (fallback)
    return {
        "status": "PASS",
        "confidence_score": 80,  # Default moderate confidence
        "reason": f"On curated list: {symbol_data.get('rationale', 'Listed in Shariah universe')}",
        "symbol": symbol,
        "methodology": "CURATED_LIST",
        "financial_ratios": None,
        "recommendation": "PASS"
    }


def get_compliance_summary(symbol: str, universe: Dict[str, Any] = None) -> str:
    """Get a human-readable compliance summary."""
    if universe is None:
        universe = load_enhanced_universe()
    
    result = check_symbol_enhanced(symbol, universe)
    
    status_emoji = {
        "PASS": "✅",
        "FAIL": "❌",
        "REVIEW": "⚠️"
    }
    
    return f"""
{status_emoji.get(result['status'], '⚪')} SHARIAH COMPLIANCE: {symbol}
   Status: {result['status']} (Confidence: {result['confidence_score']}%)
   Methodology: {result['methodology']}
   Reason: {result['reason']}
   Recommendation: {result['recommendation']}
    """.strip()


# Backward compatibility with original gate
def check_symbol(symbol: str, universe: Dict[str, Any]) -> Dict[str, Any]:
    """Backward-compatible wrapper that returns original format."""
    result = check_symbol_enhanced(symbol, universe)
    
    # Return format expected by pipeline
    return {
        "status": result["status"],
        "reason": result["reason"],
        "symbol": symbol,
        "confidence": result.get("confidence_score", 80)
    }


if __name__ == "__main__":
    # Test the enhanced gate
    universe = load_enhanced_universe()
    
    print("Enhanced Shariah Gate Test")
    print("=" * 70)
    
    test_symbols = ["NVDA", "AAPL", "MSFT", "UNKNOWN"]
    
    for symbol in test_symbols:
        result = check_symbol_enhanced(symbol, universe)
        print(f"\n{symbol}:")
        print(f"  Status: {result['status']}")
        print(f"  Confidence: {result['confidence_score']}%")
        print(f"  Reason: {result['reason'][:100]}...")
        print(f"  Recommendation: {result['recommendation']}")
