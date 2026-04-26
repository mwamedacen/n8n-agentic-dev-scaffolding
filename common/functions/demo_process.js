// DEHYDRATE:START
// Process the incoming webhook body, return a normalized result.
const body = $input.first().json.body || {};
const numbers = Array.isArray(body.numbers) ? body.numbers : [1, 2, 3];
const total = numbers.reduce((acc, n) => acc + Number(n || 0), 0);
return [{
  json: {
    received: body,
    count: numbers.length,
    total,
    average: numbers.length ? total / numbers.length : 0,
  }
}];
// DEHYDRATE:END
