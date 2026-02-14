"""
Token Guardian Billing Resolver
Work Order: #TG-BILLING-PROFILES

Provides billing resolution for subscription vs PAYG modes.
Separates "billed_cost" (actual incremental) from "payg_equivalent_cost".
"""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any


class BillingResolver:
    """
    Resolves billing costs based on provider billing profiles.
    
    For subscription providers:
      - billed_cost = 0.00 (incremental cost within subscription)
      - payg_equivalent_cost = OpenClaw usage.cost.total
    
    For PAYG providers:
      - billed_cost = OpenClaw usage.cost.total
      - payg_equivalent_cost = OpenClaw usage.cost.total
    """
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "billing.yaml"
        self.config_path = Path(config_path)
        self._config = None
        self._load_config()
    
    def _load_config(self):
        """Load billing profiles from YAML config."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Billing config not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self._config = yaml.safe_load(f)
    
    @property
    def providers(self) -> Dict[str, Any]:
        """Get provider billing profiles."""
        return self._config.get('providers', {})
    
    def get_billing_mode(self, provider: str) -> str:
        """Get billing mode for a provider."""
        return self.providers.get(provider, {}).get('billing_mode', 'payg')
    
    def get_plan_name(self, provider: str) -> Optional[str]:
        """Get plan name for a provider."""
        return self.providers.get(provider, {}).get('plan_name')
    
    def resolve_cost(
        self, 
        provider: str, 
        model: str,
        usage: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Resolve billing costs for an event.
        
        Args:
            provider: Provider name (e.g., 'minimax', 'openai')
            model: Model name (e.g., 'MiniMax-M2.1', 'gpt-5-mini')
            usage: Usage dict from OpenClaw (optional)
                   Expected fields: cost.total, input, output, cacheRead, cacheWrite
        
        Returns:
            Dict with:
                - billed_cost: Actual incremental cost (0 for subscription)
                - payg_equivalent_cost: What this would cost under PAYG
                - cost_source: Label describing the cost source(s)
                - billing_mode: 'subscription' or 'payg'
        """
        billing_mode = self.get_billing_mode(provider)
        
        # Default values
        billed_cost = 0.0
        payg_equivalent_cost = 0.0
        cost_sources = []
        
        if usage is None:
            usage = {}
        
        # Extract OpenClaw cost if available
        openclow_cost_total = usage.get('cost', {}).get('total') if usage else None
        
        if billing_mode == 'subscription':
            # Subscription: billed = 0, payg_equivalent = OpenClaw estimate
            billed_incremental = self.providers.get(provider, {}).get('billed_incremental_usd_per_token', 0.0)
            billed_cost = billed_incremental  # Should be 0.0
            
            if openclow_cost_total is not None:
                payg_equivalent_cost = openclow_cost_total
                cost_sources = ["subscription_incremental_zero", "openclaw_estimate"]
            else:
                payg_equivalent_cost = None
                cost_sources = ["subscription_incremental_zero"]
        
        elif billing_mode == 'payg':
            # PAYG: billed = OpenClaw cost
            if openclow_cost_total is not None:
                billed_cost = openclow_cost_total
                payg_equivalent_cost = openclow_cost_total
                cost_sources = ["openclaw_estimate"]
            else:
                billed_cost = None
                payg_equivalent_cost = None
                cost_sources = []
        
        else:
            # Unknown mode - use OpenClaw if available
            if openclow_cost_total is not None:
                billed_cost = openclow_cost_total
                payg_equivalent_cost = openclow_cost_total
                cost_sources = ["openclaw_estimate"]
            cost_sources.append(f"unknown_billing_mode_{billing_mode}")
        
        return {
            'provider': provider,
            'model': model,
            'billing_mode': billing_mode,
            'billed_cost': billed_cost,
            'payg_equivalent_cost': payg_equivalent_cost,
            'cost_source': ' + '.join(cost_sources) if cost_sources else None,
            'openclaw_cost_total': openclow_cost_total,
            'usage': usage
        }
    
    def aggregate_costs(
        self, 
        events: list
    ) -> Dict[str, Any]:
        """
        Aggregate costs across multiple events.
        
        Args:
            events: List of dicts with provider, model, usage
        
        Returns:
            Aggregated stats per provider/model
        """
        # Group events by provider/model
        groups = {}
        
        for event in events:
            provider = event.get('provider', 'unknown')
            model = event.get('model', 'unknown')
            key = (provider, model)
            
            if key not in groups:
                groups[key] = []
            groups[key].append(event)
        
        # Aggregate
        results = {}
        total_billed = 0.0
        total_payg_equivalent = 0.0
        
        for (provider, model), event_list in groups.items():
            billed = 0.0
            payg = 0.0
            requests = len(event_list)
            input_tokens = 0
            output_tokens = 0
            cache_tokens = 0
            
            for event in event_list:
                usage = event.get('usage')
                resolved = self.resolve_cost(provider, model, usage)
                
                if resolved['billed_cost'] is not None:
                    billed += resolved['billed_cost']
                if resolved['payg_equivalent_cost'] is not None:
                    payg += resolved['payg_equivalent_cost']
                
                # Aggregate tokens
                if usage:
                    input_tokens += usage.get('input', 0)
                    output_tokens += usage.get('output', 0)
                    cache_tokens += usage.get('cacheRead', 0) + usage.get('cacheWrite', 0)
            
            cost_source = self.providers.get(provider, {}).get('billing_mode', 'payg')
            
            results[(provider, model)] = {
                'provider': provider,
                'model': model,
                'requests': requests,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cache_tokens': cache_tokens,
                'billed_cost': billed,
                'payg_equivalent_cost': payg,
                'cost_source': cost_source
            }
            
            total_billed += billed
            total_payg_equivalent += payg
        
        results['_totals'] = {
            'total_billed_cost': total_billed,
            'total_payg_equivalent_cost': total_payg_equivalent
        }
        
        return results


# Convenience function
def resolve_billing(provider: str, model: str, usage: Optional[Dict] = None) -> Dict:
    """Quick function to resolve billing for an event."""
    resolver = BillingResolver()
    return resolver.resolve_cost(provider, model, usage)
