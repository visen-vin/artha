module.exports = {
  apps: [
    {
      name: 'feed-crypto',
      script: 'python3',
      args: '-m quant_lab.bin.feed_crypto',
      autorestart: true,
      watch: false,
    },
    {
      name: 'feed-india',
      script: 'python3',
      args: '-m quant_lab.bin.feed_india',
      autorestart: true,
      watch: false,
    },
    {
      name: 'strategy-host',
      script: 'python3',
      args: '-m quant_lab.bin.strategy_host',
      autorestart: true,
      watch: false,
    },
    {
      name: 'core-engine',
      script: 'python3',
      args: '-m quant_lab.bin.core_engine',
      autorestart: true,
      watch: false,
    },
    {
      name: 'control-bot',
      script: 'python3',
      args: '-m quant_lab.bin.control_bot',
      autorestart: true,
      watch: false,
    },
    {
      name: 'watchdog',
      script: 'python3',
      args: '-m quant_lab.bin.watchdog',
      autorestart: true,
      watch: false,
    },
  ],
};
