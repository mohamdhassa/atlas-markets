from __future__ import annotations

from pathlib import Path

TARGET = Path('tools/ibkr_bridge.py')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        print(f'{label}: already applied')
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly 1 anchor, found {count}. No file changes were written.')
    print(f'{label}: applying')
    return text.replace(old, new, 1)


def main() -> None:
    if not TARGET.exists():
        raise SystemExit(f'{TARGET} not found. Run this script from the repository root.')

    raw = TARGET.read_bytes()
    had_bom = raw.startswith(b'\xef\xbb\xbf')
    original = raw.decode('utf-8-sig')
    updated = original

    old_state = "  EClient.__init__(self,self);self.next_id=None;self.accounts=[];self.values={};self.positions=[];self.open_orders=[];self.executions=[];self.commissions={};self.errors=[];self.quotes={};self.bars={};self.contracts={};self.order_statuses={};self._events={}"
    new_state = "  EClient.__init__(self,self);self.next_id=None;self.accounts=[];self.values={};self.positions=[];self.open_orders=[];self.executions=[];self.commissions={};self.errors=[];self.quotes={};self.bars={};self.contracts={};self.order_statuses={};self.whatif_results={};self._events={}"
    updated = replace_once(updated, old_state, new_state, 'state storage')

    old_open = " def openOrder(self,orderId,contract,order,orderState):self.open_orders.append({'order_id':orderId,'symbol':contract.symbol,'sec_type':contract.secType,'side':order.action,'type':order.orderType,'quantity':float(order.totalQuantity),'limit_price':float(order.lmtPrice or 0),'aux_price':float(order.auxPrice or 0),'status':orderState.status})"
    new_open = """ def openOrder(self,orderId,contract,order,orderState):
  self.open_orders.append({'order_id':orderId,'symbol':contract.symbol,'sec_type':contract.secType,'side':order.action,'type':order.orderType,'quantity':float(order.totalQuantity),'limit_price':float(order.lmtPrice or 0),'aux_price':float(order.auxPrice or 0),'status':orderState.status})
  if getattr(order,'whatIf',False):
   def f(name):
    try:
     v=getattr(orderState,name,None);return float(v) if v not in {None,''} else None
    except:return None
   self.whatif_results[int(orderId)]={'status':getattr(orderState,'status',''),'init_margin_before':f('initMarginBefore'),'init_margin_change':f('initMarginChange'),'init_margin_after':f('initMarginAfter'),'maint_margin_before':f('maintMarginBefore'),'maint_margin_change':f('maintMarginChange'),'maint_margin_after':f('maintMarginAfter'),'equity_with_loan_before':f('equityWithLoanBefore'),'equity_with_loan_change':f('equityWithLoanChange'),'equity_with_loan_after':f('equityWithLoanAfter'),'commission':f('commission'),'min_commission':f('minCommission'),'max_commission':f('maxCommission'),'commission_currency':getattr(orderState,'commissionCurrency',''),'warning':getattr(orderState,'warningText','') or ''};self._event(f'whatif:{int(orderId)}').set()"""
    updated = replace_once(updated, old_open, new_open, 'what-if callback')

    old_check = """@app.post('/order-check')
def order_check(p:OrderPayload,x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token)
 if not cfg['simulation']:raise HTTPException(403,'ATLAS IBKR bridge refuses Live Money execution')
 if p.quantity<=0:raise HTTPException(400,'quantity must be positive')
 if p.side.upper() not in {'BUY','SELL'}:raise HTTPException(400,'side must be BUY or SELL')
 if p.order_type.upper() not in {'MKT','LMT'}:raise HTTPException(400,'order_type must be MKT or LMT')
 return {'ok':True,'simulation':True,'account_id':p.account_id or cfg.get('account_id'),'symbol':p.symbol.upper(),'side':p.side.upper(),'quantity':p.quantity,'order_type':p.order_type.upper()}"""
    new_check = """@app.post('/order-check')
def order_check(p:OrderPayload,x_atlas_bridge_token:str|None=Header(default=None)):
 auth(x_atlas_bridge_token)
 if not cfg['simulation']:raise HTTPException(403,'ATLAS IBKR bridge refuses Live Money execution')
 if p.quantity<=0:raise HTTPException(400,'quantity must be positive')
 if p.side.upper() not in {'BUY','SELL'}:raise HTTPException(400,'side must be BUY or SELL')
 if p.order_type.upper() not in {'MKT','LMT'}:raise HTTPException(400,'order_type must be MKT or LMT')
 oid=ib.next_id
 if oid is None:raise HTTPException(503,'IBKR next order id unavailable')
 ib.whatif_results.pop(int(oid),None);ib.errors=[e for e in ib.errors if int(e.get('id') or -1)!=int(oid)];prepare(f'whatif:{int(oid)}')
 o=Order();o.action=p.side.upper();o.totalQuantity=p.quantity;o.orderType=p.order_type.upper();o.transmit=True;o.whatIf=True;o.account=p.account_id or cfg.get('account_id') or '';o.tif='DAY'
 if hasattr(o,'eTradeOnly'):o.eTradeOnly=False
 if hasattr(o,'firmQuoteOnly'):o.firmQuoteOnly=False
 if o.orderType=='LMT':o.lmtPrice=float(p.limit_price or 0)
 ib.placeOrder(oid,contract(p.symbol,p.sec_type,p.exchange,p.currency),o);ib.next_id+=1
 ib._event(f'whatif:{int(oid)}').wait(8)
 result=ib.whatif_results.pop(int(oid),None);errs=[e for e in ib.errors if int(e.get('id') or -1)==int(oid)]
 if result is None:return {'ok':False,'what_if':True,'simulation':True,'account_id':p.account_id or cfg.get('account_id'),'symbol':p.symbol.upper(),'side':p.side.upper(),'quantity':p.quantity,'order_type':p.order_type.upper(),'errors':errs[-8:],'reason':'NO_WHAT_IF_RESPONSE'}
 margin={k:result.get(k) for k in ('init_margin_before','init_margin_change','init_margin_after','maint_margin_before','maint_margin_change','maint_margin_after','equity_with_loan_before','equity_with_loan_change','equity_with_loan_after')}
 return {'ok':not bool(errs),'what_if':True,'simulation':True,'account_id':p.account_id or cfg.get('account_id'),'symbol':p.symbol.upper(),'side':p.side.upper(),'quantity':p.quantity,'order_type':p.order_type.upper(),'margin':margin,'commission':{'estimate':result.get('commission'),'min':result.get('min_commission'),'max':result.get('max_commission'),'currency':result.get('commission_currency')},'warning':result.get('warning'),'errors':errs[-8:]}"""
    # Also recognize the first-run variant that used transmit=False and normalize it.
    old_check_applied = new_check.replace("o.transmit=True", "o.transmit=False")
    if old_check_applied in updated:
        print('order-check endpoint: normalizing transmit flag')
        updated = updated.replace(old_check_applied, new_check, 1)
    else:
        updated = replace_once(updated, old_check, new_check, 'order-check endpoint')

    compile(updated, str(TARGET), 'exec')

    if updated == original:
        print('IBKR WhatIf upgrade is already present and syntax is valid; no changes needed.')
        return

    backup = TARGET.with_suffix('.py.pre-whatif.bak')
    if not backup.exists():
        backup.write_bytes(raw)
        print(f'backup: {backup}')

    encoded = updated.encode('utf-8')
    if had_bom:
        encoded = b'\xef\xbb\xbf' + encoded
    TARGET.write_bytes(encoded)
    print('SUCCESS: IBKR WhatIf upgrade applied and Python syntax validated.')


if __name__ == '__main__':
    main()
