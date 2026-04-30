#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Initialize promo codes for Clever Shop"""

import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, PromoCode

def create_promo_codes():
    """Create initial promo codes"""
    
    promos = [
        {
            'code': 'WELCOME10',
            'discount_type': 'percent',
            'discount_value': 10,
            'min_order_amount': 1000,
            'max_uses': 100,
            'valid_until': datetime.utcnow() + timedelta(days=90),
            'active': True
        },
        {
            'code': 'SUMMER2026',
            'discount_type': 'percent',
            'discount_value': 15,
            'min_order_amount': 2000,
            'max_uses': 50,
            'valid_until': datetime.utcnow() + timedelta(days=60),
            'active': True
        },
        {
            'code': 'FIRST500',
            'discount_type': 'fixed',
            'discount_value': 500,
            'min_order_amount': 3000,
            'max_uses': 20,
            'valid_until': datetime.utcnow() + timedelta(days=30),
            'active': True
        },
        {
            'code': 'CLEVER2026',
            'discount_type': 'percent',
            'discount_value': 20,
            'min_order_amount': 5000,
            'max_uses': 10,
            'valid_until': datetime.utcnow() + timedelta(days=120),
            'active': True
        }
    ]
    
    with app.app_context():
        # Check if promos already exist
        existing = PromoCode.query.first()
        if existing:
            print("Promo codes already exist. Skipping...")
            return
        
        for promo_data in promos:
            promo = PromoCode(**promo_data)
            db.session.add(promo)
        
        db.session.commit()
        print(f"✓ Created {len(promos)} promo codes:")
        for p in promos:
            print(f"  - {p['code']}: {p['discount_value']}{'%' if p['discount_type'] == 'percent' else ' грн'} знижка")

if __name__ == '__main__':
    create_promo_codes()
