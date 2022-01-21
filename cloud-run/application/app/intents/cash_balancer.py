from ib_insync import Forex, MarketOrder

from intents.intent import Intent


class CashBalancer(Intent):

    _dry_run = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._dry_run = kwargs.get('dryRun', self._dry_run) if kwargs is not None else self._dry_run
        self._activity_log.update(dryRun=self._dry_run)

    def _core(self):
        self._env.logging.info('Checking cash balances...')

        account_values = self._env.get_account_values(self._env.config['account'],
                                                      rows=['NetLiquidation', 'CashBalance', 'ExchangeRate'])
        base_currency = [*account_values['NetLiquidation'].keys()][0]
        exposure = {
            k: v * account_values['ExchangeRate'][k]
            for k, v in account_values['CashBalance'].items()
            if k != base_currency
        }
        self._activity_log.update(exposure=exposure)
        trades = {
            k + base_currency: -(int(v / account_values['ExchangeRate'][k]) // 1000 * 1000)
            for k, v in exposure.items()
            if abs(v) > self._env.config['cashBalanceThresholdInBaseCurrency']
        }
        self._activity_log.update(trades=trades)
        if len(trades):
            self._env.logging.info(f'Trades to reset cash balances: {trades}')
        else:
            self._env.logging.info('No cash balances above the threshold')

        if not self._dry_run and len(trades):
            # place orders
            orders = []
            for k, v in trades.items():
                order = self._env.ibgw.placeOrder(Forex(pair=k, exchange='FXCONV'),
                                                  MarketOrder('BUY' if v > 0 else 'SELL', abs(v)))
                orders.append({
                    k: [item.nonDefaults() for item in v] if isinstance(v, list) else v.nonDefaults()
                    for k, v in order.nonDefaults().items()
                })
            self._activity_log.update(orders=orders)
            self._env.logging.info(f"Orders placed: {self._activity_log['orders']}")


if __name__ == '__main__':
    from lib.environment import Environment

    env = Environment()
    env.ibgw.connect(port=4001)
    try:
        cash_balancer = CashBalancer(dryRun=True)
        cash_balancer._core()
    except Exception as e:
        raise e
    finally:
        env.ibgw.disconnect()
