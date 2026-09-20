# Đánh giá Lab 1

`evaluate_predictions` báo cáo intent accuracy, field extraction precision /
recall / F1, missing-fields exact match, tool-needed accuracy, tool-name
accuracy, tool-argument validity, structured-output validity, unsupported
product-claim rate và abstention accuracy.

Base model và adapter phải chạy trên cùng test families và manifest hash. Mục
tiêu cứng là không family leakage và không unsupported product claim.
