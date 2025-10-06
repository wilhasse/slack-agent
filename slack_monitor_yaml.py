#!/usr/bin/env python3
"""
Slack Monitor with YAML configuration support
Monitors channels starting with specific prefixes (e.g., cslog-alertas*)
"""

import asyncio
import sys
from pathlib import Path
from typing import List

from slack_monitor import SlackMonitor
from advanced_example import AdvancedSlackMonitor
from config_loader import load_config, Config


class YamlSlackMonitor:
    """Slack Monitor configured from YAML file"""

    def __init__(self, config_file: str = "config.yaml", use_advanced: bool = True):
        """
        Initialize monitor from YAML config

        Args:
            config_file: Path to YAML configuration file
            use_advanced: Use advanced monitor with notifications/persistence
        """
        self.config = load_config(config_file)
        self.use_advanced = use_advanced
        self.monitor = None

    def _expand_channel_patterns(self, channels: List[str]) -> str:
        """
        Convert channel patterns to Slack search query

        Args:
            channels: List of channel patterns (e.g., ["cslog-alertas*", "incidents"])

        Returns:
            Query string for Slack search
        """
        if not channels:
            return None

        # For patterns with wildcards, we'll search using keywords
        # and then filter channels in the query
        patterns = []
        for channel in channels:
            if '*' in channel:
                # Extract prefix
                prefix = channel.rstrip('*')
                patterns.append(f"channels starting with '{prefix}'")
            else:
                patterns.append(f"#{channel}")

        return ", ".join(patterns)

    def _create_system_prompt(self) -> str:
        """Create system prompt with Portuguese keywords and custom rules"""
        keywords_str = ", ".join(self.config.keywords)
        channel_pattern = self.config.get_channel_pattern()

        base_prompt = f"""Você é um analisador de mensagens do Slack que ajuda a filtrar mensagens importantes.

Seu trabalho é analisar mensagens do Slack e determinar quais precisam de atenção imediata.

CANAIS A MONITORAR: {channel_pattern}

IMPORTANTE: Apenas analise mensagens dos canais especificados acima. Ignore mensagens de outros canais.

Considere uma mensagem importante se:
1. Contiver palavras-chave urgentes: {keywords_str}
2. Fizer perguntas diretas ao usuário
3. Reportar erros, incidentes ou falhas de sistema
4. Solicitar ação ou aprovação imediata
5. Contiver menções ou mensagens diretas
6. Reportar métricas críticas de negócio ou alertas

Para cada mensagem, classifique como:
- CRÍTICO: Precisa de atenção imediata
- IMPORTANTE: Deve ser revisado em breve
- NORMAL: Pode ser revisado depois
- IGNORAR: Não relevante ou spam

Seja conciso e focado em insights acionáveis.
"""

        # Add custom rules if defined
        if self.config.importance_rules:
            base_prompt += f"\n\n{self.config.importance_rules}"

        return base_prompt

    async def start(self):
        """Start monitoring"""

        # Print configuration
        print("🔍 Monitor de Slack - Configuração")
        print("=" * 60)
        print(f"📺 Canais: {self.config.get_channel_pattern()}")
        print(f"🔑 Palavras-chave: {len(self.config.keywords)} configuradas")
        print(f"⏱️  Intervalo: {self.config.check_interval} segundos")
        if self.use_advanced:
            print(f"🔔 Notificações: {'Ativadas' if self.config.enable_notifications else 'Desativadas'}")
            print(f"💾 Banco de dados: {self.config.database_path}")
        print()

        # Create monitor
        monitor_kwargs = {
            'channels_to_monitor': None,  # We'll use search instead
            'keywords': self.config.keywords,
            'check_interval': self.config.check_interval,
            'mcp_server_config': self.config.mcp_server_config
        }

        if self.use_advanced:
            monitor_kwargs['db_path'] = self.config.database_path
            monitor_kwargs['enable_notifications'] = self.config.enable_notifications
            MonitorClass = AdvancedSlackMonitor
        else:
            MonitorClass = SlackMonitor

        self.monitor = MonitorClass(**monitor_kwargs)

        # Override system prompt to include Portuguese keywords and channel filtering
        custom_prompt = self._create_system_prompt()
        self.monitor.options.system_prompt = custom_prompt

        # Start monitoring
        print("🚀 Iniciando monitoramento contínuo...")
        print("   Pressione Ctrl+C para parar")
        print()

        await self.monitor.monitor_continuously()

    async def check_once(self):
        """Check messages once and exit"""

        print("📋 Verificando mensagens uma vez...\n")

        # Create monitor
        monitor_kwargs = {
            'channels_to_monitor': None,
            'keywords': self.config.keywords,
            'check_interval': self.config.check_interval,
            'mcp_server_config': self.config.mcp_server_config
        }

        if self.use_advanced:
            monitor_kwargs['db_path'] = self.config.database_path
            monitor_kwargs['enable_notifications'] = self.config.enable_notifications
            MonitorClass = AdvancedSlackMonitor
        else:
            MonitorClass = SlackMonitor

        self.monitor = MonitorClass(**monitor_kwargs)

        # Override system prompt
        custom_prompt = self._create_system_prompt()
        self.monitor.options.system_prompt = custom_prompt

        # Check once
        await self.monitor.check_once()


async def main():
    """Main entry point"""

    import argparse

    parser = argparse.ArgumentParser(
        description="Monitor de Slack com configuração YAML"
    )
    parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Arquivo de configuração YAML (padrão: config.yaml)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Verificar uma vez e sair'
    )
    parser.add_argument(
        '--basic',
        action='store_true',
        help='Usar monitor básico (sem notificações/persistência)'
    )

    args = parser.parse_args()

    # Check if config file exists
    if not Path(args.config).exists():
        print(f"❌ Arquivo de configuração não encontrado: {args.config}")
        print()
        print("Por favor, crie o arquivo config.yaml com:")
        print("  cp config.yaml.example config.yaml")
        print("  # ou use o config.yaml já existente")
        sys.exit(1)

    # Create monitor
    monitor = YamlSlackMonitor(
        config_file=args.config,
        use_advanced=not args.basic
    )

    # Run
    try:
        if args.once:
            await monitor.check_once()
        else:
            await monitor.start()
    except KeyboardInterrupt:
        print("\n\n👋 Monitoramento parado")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
