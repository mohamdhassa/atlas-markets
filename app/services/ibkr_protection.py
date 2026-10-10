"""Read-only coverage checks for broker-reported Paper protective orders."""
import math


def position_has_native_protection(position,orders,account_id):
    try:
        quantity=float(position.get('quantity') or 0)
        if not math.isfinite(quantity) or quantity==0 or position.get('account')!=account_id:
            return False
        symbol=str(position.get('symbol') or '').upper()
        side='SELL' if quantity>0 else 'BUY'
        rows=[r for r in orders if r.get('account')==account_id and r.get('symbol')==symbol
              and str(r.get('status') or '').upper() not in {'FILLED','CANCELLED','CANCELED','INACTIVE','APICANCELLED'}]
        if len(rows)!=2 or {r.get('type') for r in rows}!={'STP','LMT'}:
            return False
        groups={r.get('oca_group') for r in rows}
        if len(groups)!=1 or not str(next(iter(groups)) or '').startswith('atlas-protect-'):
            return False
        for row in rows:
            remaining=float(row.get('quantity') or 0)-float(row.get('filled') or 0)
            price=float(row.get('aux_price') if row.get('type')=='STP' else row.get('limit_price'))
            if (not math.isfinite(price) or price<=0 or row.get('side')!=side
                    or row.get('sec_type')!='STK' or row.get('oca_type')!=2
                    or row.get('order_ref')!=row.get('oca_group') or row.get('tif')!='GTC'
                    or row.get('outside_rth') is not False
                    or str(row.get('status') or '').upper() not in {'SUBMITTED','PRESUBMITTED'}
                    or not math.isclose(remaining,abs(quantity),rel_tol=0,abs_tol=1e-8)):
                return False
        return True
    except (TypeError,ValueError):
        return False
