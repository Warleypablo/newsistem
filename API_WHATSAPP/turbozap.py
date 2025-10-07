#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TurboZap - Módulo de Envio Automático de Mensagens WhatsApp
Sistema inteligente para envio de mensagens de cobrança via WhatsApp
Integrado com Evolution API e banco de dados PostgreSQL

Autor: Sistema TurboX
Versão: 2.0
Data: 2024
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import requests
import random
import time
import logging
import json
import argparse
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('turbozap.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Carregar variáveis do .env
load_dotenv()

class TurboZapConfig:
    """Configurações do TurboZap"""
    
    def __init__(self):
        self.db_host = os.getenv("DB_HOST")
        self.db_name = os.getenv("DB_NAME")
        self.db_user = os.getenv("DB_USER")
        self.db_password = os.getenv("DB_PASSWORD")
        self.db_port = os.getenv("DB_PORT")
        
        self.evolution_server_url = os.getenv('EVOLUTION_API_URL')
        self.evolution_instance_id = os.getenv('EVOLUTION_INSTANCE')
        self.evolution_token = os.getenv('EVOLUTION_API_KEY')
        
        self.validate_config()
    
    def validate_config(self):
        """Valida se todas as configurações necessárias estão presentes"""
        # Variáveis obrigatórias
        required_vars = [
            'DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD',
            'EVOLUTION_API_URL', 'EVOLUTION_INSTANCE', 'EVOLUTION_API_KEY'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(f"Variáveis de ambiente obrigatórias não encontradas: {', '.join(missing_vars)}")

class DatabaseManager:
    """Gerenciador de conexão com banco de dados"""
    
    def __init__(self, config: TurboZapConfig):
        self.config = config
        self.conn = None
        self.cursor = None
        self.connect()
    
    def connect(self):
        """Estabelece conexão com o banco de dados"""
        try:
            self.conn = psycopg2.connect(
                host=os.getenv('DB_HOST'),
                database=os.getenv('DB_NAME'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                port=os.getenv('DB_PORT', 5432)
            )
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            logger.info("✅ Conexão com banco de dados estabelecida com sucesso")
        except Exception as e:
            logger.error(f"❌ Erro ao conectar com banco de dados: {e}")
            raise
    
    def close(self):
        """Fecha conexão com o banco de dados"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("🔌 Conexão com banco de dados fechada")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class WhatsAppSender:
    """Classe responsável pelo envio de mensagens WhatsApp via Evolution API"""
    
    def __init__(self, config: TurboZapConfig):
        self.config = config
        self.api_url = config.evolution_server_url
        self.instance_id = config.evolution_instance_id
        self.token = config.evolution_token
        # Remove https:// se já estiver presente na URL
        api_url_clean = self.api_url.replace('https://', '').replace('http://', '')
        self.base_url = f"https://{api_url_clean}/message/sendText/{self.instance_id}"
        self.headers = {
            "apikey": self.token,
            "Content-Type": "application/json"
        }
        self.sent_count = 0
        self.error_count = 0
    
    def format_phone_number(self, phone: str) -> str:
        """Formata número de telefone removendo caracteres especiais"""
        if not phone:
            return ""
        
        # Remove todos os caracteres não numéricos
        clean_phone = ''.join(filter(str.isdigit, phone))
        
        # Adiciona código do país se necessário (Brasil = 55)
        if len(clean_phone) == 11 and clean_phone.startswith('11'):
            clean_phone = '55' + clean_phone
        elif len(clean_phone) == 10:
            clean_phone = '5511' + clean_phone
        
        return clean_phone
    
    def format_message(self, template: str, cliente: Dict) -> str:
        """Formata mensagem substituindo variáveis do template"""
        try:
            return template.format(
                nome=cliente['cliente_nome'],
                valor=float(cliente['total']),
                vencimento=cliente['data_vencimento'].strftime("%d/%m/%Y"),
                link_pagamento=cliente['link_pagamento']
            )
        except Exception as e:
            logger.error(f"❌ Erro ao formatar mensagem para {cliente['cliente_nome']}: {e}")
            return template
    
    def send_message(self, cliente: Dict, mensagem: str) -> bool:
        """Envia mensagem WhatsApp para um cliente"""
        numero_cliente = self.format_phone_number(cliente['telefone'])
        nome_cliente = cliente['cliente_nome']
        
        if not numero_cliente:
            logger.warning(f"⚠️ Número de telefone inválido para {nome_cliente}")
            return False
        
        mensagem_formatada = self.format_message(mensagem, cliente)
        
        payload = {
            "number": numero_cliente,
            "options": {
                "delay": random.randint(100, 300),
                "presence": "composing",
                "linkPreview": True
            },
            "text": mensagem_formatada
        }
        
        try:
            response = requests.post(
                self.base_url,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Mensagem enviada para {nome_cliente} ({numero_cliente})")
                self.sent_count += 1
                return True
            else:
                logger.error(f"❌ Erro ao enviar para {nome_cliente}: {response.status_code} - {response.text}")
                self.error_count += 1
                return False
                
        except requests.exceptions.Timeout:
            logger.error(f"⏰ Timeout ao enviar mensagem para {nome_cliente}")
            self.error_count += 1
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro de conexão ao enviar para {nome_cliente}: {e}")
            self.error_count += 1
            return False
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas de envio"""
        return {
            'sent': self.sent_count,
            'errors': self.error_count,
            'total': self.sent_count + self.error_count
        }

class ClienteManager:
    """Gerenciador de consultas de clientes"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def buscar_clientes_por_vencimento(self, data_vencimento: str) -> List[Dict]:
        """Busca clientes com vencimento específico"""
        query = """
            SELECT id, cliente_nome, telefone, data_vencimento, total, link_pagamento, status
            FROM caz_receber
            WHERE data_vencimento = %s
            AND telefone IS NOT NULL
            AND telefone != ''
            AND pago = '0'
            AND nao_pago > 0
            ORDER BY total DESC
        """
        
        try:
            self.db_manager.cursor.execute(query, (data_vencimento,))
            clientes = self.db_manager.cursor.fetchall()
            logger.info(f"📋 Encontrados {len(clientes)} clientes para {data_vencimento}")
            return clientes
        except Exception as e:
            logger.error(f"❌ Erro ao buscar clientes: {e}")
            return []
    
    def buscar_clientes_inadimplentes(self, dias_atraso: int = 1) -> List[Dict]:
        """Busca clientes inadimplentes por número de dias"""
        data_limite = (datetime.now() - timedelta(days=dias_atraso)).strftime("%Y-%m-%d")
        
        query = """
            SELECT id, cliente_nome, telefone, data_vencimento, total, link_pagamento, status
            FROM caz_receber
            WHERE data_vencimento <= %s
            AND telefone IS NOT NULL
            AND telefone != ''
            AND pago = '0'
            AND nao_pago > 0
            AND status != 'ACQUITTED'
            ORDER BY data_vencimento ASC, total DESC
        """
        
        try:
            self.db_manager.cursor.execute(query, (data_limite,))
            clientes = self.db_manager.cursor.fetchall()
            logger.info(f"📋 Encontrados {len(clientes)} clientes inadimplentes há {dias_atraso}+ dias")
            return clientes
        except Exception as e:
            logger.error(f"❌ Erro ao buscar clientes inadimplentes: {e}")
            return []

class MessageTemplates:
    """Templates de mensagens para diferentes períodos de cobrança"""
    
    TEMPLATES = {
        "D-3": {
            "message": "Oi {nome}, tudo certo por aí?\n\n🔔 Passando só pra lembrar que o boleto da Turbo vence em 3 dias:\n💰 Valor: R$ {valor:.2f}\n📅 Vencimento: {vencimento}\n\nQualquer dúvida, estamos por aqui 👊\n\n🔗 {link_pagamento}\n\nObrigado pela parceria de sempre! 🚀\n— Time Financeiro | Turbo Partners",
            "description": "Lembrete 3 dias antes do vencimento"
        },
        "D+0": {
            "message": "Oi {nome}, tudo certo?\n\n⏰ Passando aqui só pra avisar que o boleto da Turbo vence hoje:\n💰 Valor: R$ {valor:.2f}\n📅 Vencimento: {vencimento}\n\nSegue o link pra facilitar:\n🔗 {link_pagamento}\n\nQualquer coisa, é só chamar por aqui 👍\n— Time Financeiro | Turbo Partners",
            "description": "Aviso no dia do vencimento"
        },
        "D+1": {
            "message": "Oi {nome}, tudo certo?\n\n⚠️ Ontem venceu o boleto da Turbo e ainda não localizamos o pagamento:\n💰 Valor: R$ {valor:.2f}\n📅 Vencimento: {vencimento}\n\nCaso já tenha pago, é só nos enviar o comprovante por aqui.\n\nSe ainda não conseguiu, segue o link:\n🔗 {link_pagamento}\n\n⚡ Importante: caso a pendência não seja regularizada até o 7º dia após o vencimento, os serviços serão pausados automaticamente.\n\nQualquer dúvida, estamos à disposição.\n— Time Financeiro | Turbo Partners",
            "description": "Primeiro aviso de atraso"
        },
        "D+7": {
            "message": "Oi {nome}, tudo certo?\n\n🚫 O boleto da Turbo segue em aberto há 7 dias e os serviços estão sendo pausados temporariamente:\n💰 Valor: R$ {valor:.2f}\n📅 Vencimento: {vencimento}\n\nCaso já tenha feito o pagamento, é só nos enviar o comprovante para reativarmos as entregas.\n\nLink do boleto:\n🔗 {link_pagamento}\n\nQualquer dúvida, seguimos à disposição.\n— Time Financeiro | Turbo Partners",
            "description": "Suspensão de serviços"
        },
        "D+14": {
            "message": "Oi {nome}, tudo certo?\n\n⚖️ O boleto da Turbo segue em aberto há 14 dias:\n💰 Valor: R$ {valor:.2f}\n📅 Vencimento: {vencimento}\n\nConforme previsto contratualmente, o serviço já está pausado. Caso o pagamento não seja regularizado nos próximos 7 dias, o contrato será rescindido por justa causa, com início imediato do processo de cobrança judicial.\n\nAinda há tempo para resolver de forma amigável:\n🔗 {link_pagamento}\n\nFicamos no aguardo de uma posição.\n— Time Financeiro | Turbo Partners",
            "description": "Aviso pré-judicial"
        },
        "D+21": {
            "message": "Prezado(a) {nome},\n\n⚖️ Comunicamos que, diante da inadimplência do boleto vencido em {vencimento}, no valor de R$ {valor:.2f}, e transcorridos 21 dias sem regularização, o contrato firmado com a Turbo Partners encontra-se rescindido por justa causa.\n\nInformamos que os serviços foram encerrados em caráter definitivo, e o processo de cobrança judicial foi instaurado para a recuperação integral dos valores em aberto, acrescidos de multa, juros legais e honorários advocatícios.\n\nEm caso de dúvidas ou negociação formal, estamos à disposição para redirecionar a tratativa ao nosso setor jurídico.\n\nAtenciosamente,\nDepartamento Financeiro | Turbo Partners",
            "description": "Notificação judicial"
        }
    }
    
    @classmethod
    def get_message(cls, periodo: str) -> str:
        """Retorna mensagem para o período especificado"""
        template = cls.TEMPLATES.get(periodo)
        if template:
            return template["message"]
        raise ValueError(f"Período {periodo} não encontrado nos templates")
    
    @classmethod
    def get_description(cls, periodo: str) -> str:
        """Retorna descrição do período"""
        template = cls.TEMPLATES.get(periodo)
        if template:
            return template["description"]
        return "Período desconhecido"
    
    @classmethod
    def list_periods(cls) -> List[str]:
        """Lista todos os períodos disponíveis"""
        return list(cls.TEMPLATES.keys())

class TurboZap:
    """Classe principal do sistema TurboZap"""
    
    def __init__(self):
        self.config = TurboZapConfig()
        self.db_manager = None
        self.whatsapp_sender = None
        self.cliente_manager = None
        self.message_templates = MessageTemplates()
    
    def initialize(self):
        """Inicializa todos os componentes do sistema"""
        try:
            self.db_manager = DatabaseManager(self.config)
            self.whatsapp_sender = WhatsAppSender(self.config)
            self.cliente_manager = ClienteManager(self.db_manager)
            logger.info("🚀 TurboZap inicializado com sucesso")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar TurboZap: {e}")
            return False
    
    def calculate_target_date(self, periodo: str) -> str:
        """Calcula data alvo baseada no período"""
        if "D+" in periodo:
            dias_num = int(periodo.split("+")[1])
            return (datetime.now() - timedelta(days=dias_num)).strftime("%Y-%m-%d")
        elif "D-" in periodo:
            dias_num = int(periodo.split("-")[1])
            return (datetime.now() + timedelta(days=dias_num)).strftime("%Y-%m-%d")
        else:
            return datetime.now().strftime("%Y-%m-%d")
    
    def send_messages_for_period(self, periodo: str, max_messages: int = None) -> Dict:
        """Envia mensagens para um período específico"""
        if not self.db_manager or not self.whatsapp_sender or not self.cliente_manager:
            raise RuntimeError("TurboZap não foi inicializado. Chame initialize() primeiro.")
        
        data_vencimento = self.calculate_target_date(periodo)
        mensagem = self.message_templates.get_message(periodo)
        descricao = self.message_templates.get_description(periodo)
        
        logger.info(f"📅 Processando período {periodo} ({descricao}) - Data: {data_vencimento}")
        
        clientes = self.cliente_manager.buscar_clientes_por_vencimento(data_vencimento)
        
        if not clientes:
            logger.info(f"ℹ️ Nenhum cliente encontrado para {periodo}")
            return {'sent': 0, 'errors': 0, 'skipped': 0}
        
        sent_count = 0
        error_count = 0
        skipped_count = 0
        
        # Limitar número de mensagens se especificado
        if max_messages and len(clientes) > max_messages:
            clientes = clientes[:max_messages]
            logger.info(f"⚠️ Limitando envios a {max_messages} mensagens")
        
        for i, cliente in enumerate(clientes, 1):
            if cliente['status'] == 'ACQUITTED':
                logger.info(f"💳 Boleto já pago para {cliente['cliente_nome']}. Ignorando.")
                skipped_count += 1
                continue
            
            logger.info(f"📤 Enviando {i}/{len(clientes)} - {cliente['cliente_nome']}")
            
            success = self.whatsapp_sender.send_message(cliente, mensagem)
            
            if success:
                sent_count += 1
            else:
                error_count += 1
            
            # Delay entre envios para evitar spam
            if i < len(clientes):  # Não aguardar após o último envio
                delay = random.uniform(10, 30)
                logger.info(f"⏰ Aguardando {delay:.1f}s antes do próximo envio...")
                time.sleep(delay)
        
        stats = {
            'sent': sent_count,
            'errors': error_count,
            'skipped': skipped_count,
            'total_processed': len(clientes)
        }
        
        logger.info(f"📊 Resumo {periodo}: {sent_count} enviadas, {error_count} erros, {skipped_count} ignoradas")
        return stats
    
    def run_all_periods(self, max_messages_per_period: int = None) -> Dict:
        """Executa envio para todos os períodos configurados"""
        if not self.initialize():
            return {'error': 'Falha na inicialização'}
        
        total_stats = {'sent': 0, 'errors': 0, 'skipped': 0, 'periods': {}}
        
        try:
            for periodo in self.message_templates.list_periods():
                try:
                    stats = self.send_messages_for_period(periodo, max_messages_per_period)
                    total_stats['periods'][periodo] = stats
                    total_stats['sent'] += stats['sent']
                    total_stats['errors'] += stats['errors']
                    total_stats['skipped'] += stats['skipped']
                except Exception as e:
                    logger.error(f"❌ Erro ao processar período {periodo}: {e}")
                    total_stats['periods'][periodo] = {'error': str(e)}
            
            logger.info(f"🎯 TOTAL GERAL: {total_stats['sent']} enviadas, {total_stats['errors']} erros, {total_stats['skipped']} ignoradas")
            
        finally:
            if self.db_manager:
                self.db_manager.close()
        
        return total_stats
    
    def run_specific_period(self, periodo: str, max_messages: int = None) -> Dict:
        """Executa envio para um período específico"""
        if not self.initialize():
            return {'error': 'Falha na inicialização'}
        
        try:
            return self.send_messages_for_period(periodo, max_messages)
        finally:
            if self.db_manager:
                self.db_manager.close()


def main():
    """Função principal do sistema"""
    parser = argparse.ArgumentParser(
        description='TurboZap - Sistema de Envio Automático de Mensagens WhatsApp',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python turbozap.py                    # Enviar para todos os períodos
  python turbozap.py --periodo D+7      # Enviar apenas para D+7
  python turbozap.py --periodo D-3      # Enviar apenas para D-3

Períodos disponíveis: D-3, D+0, D+1, D+7, D+14, D+21

Configuração:
  Configure as variáveis de ambiente no arquivo .env ou diretamente no sistema.
  Veja o arquivo .env.example para referência.
        """
    )
    
    parser.add_argument(
        '--periodo',
        type=str,
        help='Período específico para envio (ex: D+7, D-3)'
    )
    
    args = parser.parse_args()
    
    # Se for apenas help, não precisa validar configurações
    if len(sys.argv) == 1 or '--help' in sys.argv or '-h' in sys.argv:
        return
    
    logger.info("🚀 Iniciando TurboZap - Sistema de Envio Automático WhatsApp")
    
    try:
        turbozap = TurboZap()
        
        if args.periodo:
            if args.periodo in MessageTemplates.list_periods():
                logger.info(f"📋 Executando período específico: {args.periodo}")
                stats = turbozap.run_specific_period(args.periodo)
            else:
                logger.error(f"❌ Período inválido: {args.periodo}")
                logger.info(f"Períodos disponíveis: {', '.join(MessageTemplates.list_periods())}")
                return
        else:
            # Executar todos os períodos
            logger.info("📋 Executando todos os períodos")
            stats = turbozap.run_all_periods()
        
        logger.info("✅ TurboZap finalizado")
        return stats
        
    except Exception as e:
        logger.error(f"❌ Erro durante execução: {e}")
        return {'error': str(e)}


if __name__ == "__main__":
    main()
