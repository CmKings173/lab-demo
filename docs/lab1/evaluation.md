# Đánh giá Lab 1

`evaluate_predictions` báo cáo intent accuracy, field extraction precision /
recall / F1, missing-fields exact match, tool-needed accuracy, tool-name
accuracy/sequence accuracy, tool-argument schema validity, exact/semantic match,
structured-output validity, unsupported product-claim rate và abstention accuracy.

Prediction cung cấp tool calls và structured output thật; evaluator không nhận
boolean tự khai `tool_arguments_valid`. Structured-output denominator chỉ gồm các
gold case có `expects_structured_output=true`; abstention dùng gold label.

Base model và adapter phải chạy trên cùng test families và manifest hash. Mục
tiêu cứng là không family leakage và không unsupported product claim.
