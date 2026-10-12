const set = (id, value) => { document.getElementById(id).textContent = value }

fetch('../results/benchmark.json')
  .then(response => {
    if (!response.ok) throw new Error('Missing result')
    return response.json()
  })
  .then(data => {
    const before = data.before
    const after = data.after
    const format = value => Number(value).toLocaleString('en-US')
    set('speedup', `${data.median_speedup}×`)
    set('before-ms', before.median_ms.toFixed(3))
    set('after-ms', after.median_ms.toFixed(3))
    set('before-access', before.plan.query_block.table.access_type)
    set('after-access', after.plan.query_block.table.access_type)
    set('before-rows', format(before.plan.query_block.table.rows_examined_per_scan))
    set('after-rows', format(after.plan.query_block.table.rows_examined_per_scan))
    set('same-rows', format(after.rows))
    document.getElementById('before-bar').style.width = '100%'
    document.getElementById('after-bar').style.width = `${Math.max(3, 100 * after.median_ms / before.median_ms)}%`
  })
  .catch(() => { document.getElementById('error').hidden = false })
