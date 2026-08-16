from flask import Blueprint, jsonify, request
from database import execute_query

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin')
def admin_panel():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>LipaViews Admin Dashboard</title>
        <style>
            body { font-family: sans-serif; background: #0f172a; color: white; padding: 16px; margin: 0; }
            h2, h3 { color: #38bdf8; }
            .card { background: #1e293b; padding: 12px; border-radius: 8px; margin-bottom: 16px; border: 1px solid #334155; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
            th, td { border: 1px solid #334155; padding: 8px; text-align: left; }
            th { background: #0f172a; color: #38bdf8; }
            .btn { background: #16a34a; color: white; border: none; padding: 6px 10px; cursor: pointer; border-radius: 4px; font-weight: bold; }
            .btn-blue { background: #0284c7; }
            select { background: #0f172a; color: white; border: 1px solid #334155; padding: 4px; border-radius: 4px; }
        </style>
    </head>
    <body>
        <h2>LipaViews Management</h2>
        <div class="card">
            <p style="margin:0;"><b>Paybill:</b> 501101 | <b>Account:</b> 00001</p>
        </div>

        <button onclick="loadData()" class="btn btn-blue" style="margin-bottom: 12px;">Refresh All Data</button>

        <h3>Registered Users & Tier Management</h3>
        <div id="users-table">Loading users...</div>

        <h3>Pending Sunday Payout Batch (MiniPay)</h3>
        <div id="payouts-table">Loading payout batch...</div>

        <script>
            async function loadData() {
                const resU = await fetch('/api/admin/users');
                const users = await resU.json();
                let htmlU = '<table><tr><th>TG ID</th><th>Name</th><th>Phone</th><th>Balance</th><th>Tier</th><th>Update Tier</th></tr>';
                users.forEach(u => {
                    htmlU += `<tr>
                        <td>${u.telegram_id}</td>
                        <td>${u.full_name || 'N/A'}</td>
                        <td>${u.phone_number || 'N/A'}</td>
                        <td>KES ${parseFloat(u.balance).toFixed(2)}</td>
                        <td><b style="color:#38bdf8">${u.pro_tier.toUpperCase()}</b></td>
                        <td>
                            <select onchange="updateTier(${u.telegram_id}, this.value)">
                                <option value="free" ${u.pro_tier === 'free' ? 'selected' : ''}>Free (0 KSH)</option>
                                <option value="pro_1" ${u.pro_tier === 'pro_1' ? 'selected' : ''}>Pro 1 (100 KSH)</option>
                                <option value="pro_2" ${u.pro_tier === 'pro_2' ? 'selected' : ''}>Pro 2 (200 KSH)</option>
                            </select>
                        </td>
                    </tr>`;
                });
                htmlU += '</table>';
                document.getElementById('users-table').innerHTML = htmlU;

                const resP = await fetch('/api/admin/payouts');
                const payouts = await resP.json();
                let htmlP = '<table><tr><th>Tx ID</th><th>TG ID</th><th>Name</th><th>Phone</th><th>Wallet</th><th>Amount</th><th>Action</th></tr>';
                payouts.forEach(p => {
                    htmlP += `<tr>
                        <td>#${p.id}</td>
                        <td>${p.telegram_id}</td>
                        <td>${p.full_name || 'N/A'}</td>
                        <td>${p.phone_number || 'N/A'}</td>
                        <td>${p.minipay_wallet || 'N/A'}</td>
                        <td>KES ${parseFloat(p.amount).toFixed(2)}</td>
                        <td><button class="btn" onclick="markPaid(${p.id})">Mark Paid via MiniPay</button></td>
                    </tr>`;
                });
                htmlP += '</table>';
                document.getElementById('payouts-table').innerHTML = htmlP;
            }

            async function updateTier(tgId, tier) {
                await fetch('/api/admin/update-tier', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ telegram_id: tgId, pro_tier: tier })
                });
                loadData();
            }

            async function markPaid(txId) {
                await fetch('/api/admin/mark-paid', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ transaction_id: txId })
                });
                loadData();
            }

            loadData();
        </script>
    </body>
    </html>
    '''

@admin_bp.route('/api/admin/users', methods=['GET'])
def admin_get_users():
    users = execute_query("SELECT telegram_id, full_name, phone_number, balance, pro_tier FROM users;", fetchall=True)
    return jsonify(users)

@admin_bp.route('/api/admin/update-tier', methods=['POST'])
def admin_update_tier():
    data = request.get_json() or {}
    tg_id = data.get('telegram_id')
    tier = data.get('pro_tier')
    execute_query("UPDATE users SET pro_tier = %s WHERE telegram_id = %s;", (tier, tg_id), commit=True)
    return jsonify({"status": "success"})

@admin_bp.route('/api/admin/payouts', methods=['GET'])
def admin_get_payouts():
    query = """
        SELECT tx.id, tx.telegram_id, tx.amount, u.full_name, u.phone_number, u.minipay_wallet
        FROM transactions tx
        JOIN users u ON tx.telegram_id = u.telegram_id
        WHERE tx.status = 'pending' AND tx.type = 'minipay_withdraw';
    """
    payouts = execute_query(query, fetchall=True)
    return jsonify(payouts)

@admin_bp.route('/api/admin/mark-paid', methods=['POST'])
def admin_mark_paid():
    data = request.get_json() or {}
    tx_id = data.get('transaction_id')
    execute_query("UPDATE transactions SET status = 'completed' WHERE id = %s;", (tx_id,), commit=True)
    return jsonify({"status": "success"})
